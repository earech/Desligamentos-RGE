import os
import sys
import base64
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

MUNICIPIO = "Sao Marcos"
DIAS_FRENTE = 5
URL = "https://spir.cpfl.com.br/Publico/ConsultaDesligamentoProgramado/Visualizar/4"

def formatar_data(dt):
    return dt.strftime("%d/%m/%Y")

def consultar(page):
    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)
    page.goto(URL, wait_until="networkidle", timeout=30000)
    page.locator("label", has_text="Por Localizacao").click()
    page.wait_for_timeout(500)
    page.locator("input[name='DataInicio']").first.fill(formatar_data(hoje))
    page.locator("input[name='DataFim']").first.fill(formatar_data(fim))
    page.locator("select[name='Municipio']").first.select_option(label="São Marcos")
    page.wait_for_timeout(300)
    page.locator("button:has-text('Pesquisar')").first.click()
    page.wait_for_timeout(5000)
    if page.locator("text=Nenhum desligamento programado").count() > 0:
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
        corpo = "Nenhum desligamento em " + MUNICIPIO + ". Periodo: " + periodo
        tem_alerta = False
    else:
        linhas = ["ALERTA: " + str(len(desligamentos)) + " desligamento(s) em " + MUNICIPIO]
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
