import os
import sys
import base64
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

DIAS_FRENTE = 5
URL = "https://spir.cpfl.com.br/Publico/ConsultaDesligamentoProgramado/Visualizar/4"

def formatar_data(dt):
    return dt.strftime("%d/%m/%Y")

def consultar(page):
    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)
    page.goto(URL, wait_until="networkidle", timeout=30000)

    # Força o clique via JS, ignorando visibilidade
    page.evaluate("document.getElementById('TipoConsulta_Localizacao').click()")
    page.wait_for_timeout(800)

    page.evaluate("document.querySelector('input[name=DataInicio]').value = '" + formatar_data(hoje) + "'")
    page.evaluate("document.querySelector('input[name=DataFim]').value = '" + formatar_data(fim) + "'")

    # Seleciona Sao Marcos no select
    page.evaluate("""
        var sel = document.querySelector('select[name=Municipio]');
        for (var i = 0; i < sel.options.length; i++) {
            if (sel.options[i].text.trim() === 'São Marcos') {
                sel.selectedIndex = i;
                break;
            }
        }
    """)
    page.wait_for_timeout(300)

    # Submete o formulario via JS
    page.evaluate("document.querySelector('button[type=submit]').click()")
    page.wait_for_timeout(6000)

    if page.get_by_text("Nenhum desligamento programado").count() > 0:
        return []

    desligamentos = []
    linhas = page.locator("table tr").all()
    cabecalhos = []
    for i, linha in enumerate(linhas):
        celulas = [c.inner_text().strip() for c in linha.locator("td, th").all()]
        if not celulas:
            continue
        if i == 0:
            cabecalhos = celulas
        else:
            item = dict(zip(cabecalhos, celulas)) if cabecalhos else {"info": " | ".join(celulas)}
            desligamentos.append(item)
    return desligamentos

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(locale="pt-BR").new_page()
        try:
            desligamentos = consultar(page)
        except Exception as e:
            print("Erro: " + str(e))
            browser.close()
            sys.exit(1)
        browser.close()

    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)
    periodo = formatar_data(hoje) + " ate " + formatar_data(fim)

    if not desligamentos:
        corpo = "Nenhum desligamento em Sao Marcos. Periodo: " + periodo
        tem_alerta = False
    else:
        linhas = ["ALERTA: " + str(len(desligamentos)) + " desligamento(s) em Sao Marcos"]
        linhas.append("Periodo: " + periodo)
        for i, d in enumerate(desligamentos, 1):
            linhas.append("--- Desligamento " + str(i) + " ---")
            for k, v in d.items():
                linhas.append("  " + k + ": " + v)
        linhas.append("Veja em: " + URL)
        corpo = "\n".join(linhas)
        tem_alerta = True

    print(corpo)

    gh = os.environ.get("GITHUB_OUTPUT", "")
    if gh:
        b64 = base64.b64encode(corpo.encode("utf-8")).decode()
        with open(gh, "a") as f:
            f.write("status=" + ("alerta" if tem_alerta else "ok") + "\n")
            f.write("tem_desligamento=" + ("true" if tem_alerta else "false") + "\n")
            f.write("corpo_b64=" + b64 + "\n")

    sys.exit(0)

if __name__ == "__main__":
    main()
