import os, sys, base64
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

DIAS_FRENTE = 5
URL = "https://spir.cpfl.com.br/Publico/ConsultaDesligamentoProgramado/Visualizar/4"

def formatar_data(dt):
    return dt.strftime("%d/%m/%Y")

def salvar(page, nome):
    page.screenshot(path=nome + ".png", full_page=True)
    with open(nome + ".html", "w", encoding="utf-8") as f:
        f.write(page.content())
    print("Salvo: " + nome)

def consultar(page):
    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)

    print("Carregando pagina...")
    page.goto(URL, wait_until="networkidle", timeout=40000)
    page.wait_for_timeout(3000)
    salvar(page, "01_pagina_inicial")

    print("Preenchendo formulario via JS...")
    page.evaluate("""
        var radio = document.getElementById('TipoConsulta_Localizacao');
        if (!radio) { console.log('radio nao encontrado'); } else {
        radio.checked = true;
        radio.dispatchEvent(new Event('change', {bubbles:true}));

        var inputs = document.querySelectorAll('input[type=text]');
        inputs[0].value = '""" + formatar_data(hoje) + """';
        inputs[0].dispatchEvent(new Event('change', {bubbles:true}));
        inputs[1].value = '""" + formatar_data(fim) + """';
        inputs[1].dispatchEvent(new Event('change', {bubbles:true}));

        var sel = document.getElementById('IdMunicipio');
        for (var i = 0; i < sel.options.length; i++) {
            if (sel.options[i].text.indexOf('Marcos') !== -1) {
                sel.selectedIndex = i;
                sel.dispatchEvent(new Event('change', {bubbles:true}));
                break;
            }
        }

        var bairro = document.getElementById('Bairro');
        bairro.value = 'Industrial';
        bairro.dispatchEvent(new Event('change', {bubbles:true}));
        }
    """)
    page.wait_for_timeout(1000)
    salvar(page, "02_apos_preenchimento")

    print("Submetendo formulario...")
    page.evaluate("""
        var btn = document.querySelector('button[type=submit]') ||
                  document.querySelector('input[type=submit]') ||
                  document.querySelector('button.btn-primary') ||
                  document.querySelector('button');
        if (btn) btn.click();
    """)
    page.wait_for_timeout(7000)

    salvar(page, "03_apos_pesquisa")

    sem_resultado = page.locator("text=Nenhum desligamento programado").is_visible()
    print("Sem resultado visivel: " + str(sem_resultado))

    # Loga todo o texto visivel da pagina para diagnostico
    texto_pagina = page.locator("body").inner_text()
    print("=== TEXTO DA PAGINA ===")
    print(texto_pagina[:3000])
    print("=== FIM ===")

    if sem_resultado:
        return []

    desligamentos = []
    linhas = page.locator("table tr").all()
    print("Linhas na tabela: " + str(len(linhas)))
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
            page.screenshot(path="erro.png", full_page=True)
            print("Erro: " + str(e))
            browser.close()
            sys.exit(1)
        browser.close()

    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)
    periodo = formatar_data(hoje) + " ate " + formatar_data(fim)

    if not desligamentos:
        corpo = "Nenhum desligamento em Sao Marcos - Industrial. Periodo: " + periodo
        tem_alerta = False
    else:
        linhas = ["ALERTA: " + str(len(desligamentos)) + " desligamento(s) em Sao Marcos - Industrial"]
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
