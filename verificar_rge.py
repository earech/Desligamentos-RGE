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
    salvar(page, "01_pagina_inicial")

    print("Clicando radio Por Localizacao via JS...")
    page.evaluate("""
        var el = document.getElementById('TipoConsulta_Localizacao');
        if (el) {
            el.checked = true;
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new Event('click', {bubbles: true}));
        } else {
            console.log('Radio nao encontrado');
        }
    """)
    page.wait_for_timeout(1500)
    salvar(page, "02_apos_radio")

    print("Campos visiveis apos radio:")
    inputs = page.evaluate("""
        Array.from(document.querySelectorAll('input, select')).map(function(el) {
            return el.name + ' | ' + el.id + ' | ' + el.type + ' | visible:' + (el.offsetParent !== null);
        })
    """)
    for inp in inputs:
        print("  " + inp)

    print("Preenchendo datas...")
    page.evaluate("""
        var campos = document.querySelectorAll('input[type=text], input[type=date]');
        campos.forEach(function(c) {
            console.log('campo: ' + c.name + ' id:' + c.id);
        });
    """)

    # Tenta preencher por id e por name com varias variações
    for seletor in ["#DataInicio", "input[name='DataInicio']", "input[name='dataInicio']", "input[id*='nicio']"]:
        count = page.locator(seletor).count()
        if count > 0:
            print("DataInicio encontrado com: " + seletor)
            page.locator(seletor).first.fill(formatar_data(hoje))
            break

    for seletor in ["#DataFim", "input[name='DataFim']", "input[name='dataFim']", "input[id*='im']"]:
        count = page.locator(seletor).count()
        if count > 0:
            print("DataFim encontrado com: " + seletor)
            page.locator(seletor).first.fill(formatar_data(fim))
            break

    salvar(page, "03_apos_datas")

    print("Selecionando municipio...")
    page.evaluate("""
        var sels = document.querySelectorAll('select');
        sels.forEach(function(sel) {
            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].text.indexOf('Marcos') !== -1) {
                    sel.selectedIndex = i;
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                    console.log('Municipio selecionado: ' + sel.options[i].text);
                    break;
                }
            }
        });
    """)
    page.wait_for_timeout(500)

    for seletor in ["#Bairro", "input[name='Bairro']"]:
        if page.locator(seletor).count() > 0:
            page.locator(seletor).first.fill("Industrial")
            break

    salvar(page, "04_apos_municipio")
    
    print("Clicando pesquisar...")
    page.evaluate("""
        var btns = document.querySelectorAll('button, input[type=submit], input[type=button]');
        btns.forEach(function(b) { console.log('btn: ' + b.type + ' text:' + b.innerText + ' value:' + b.value); });
    """)
    page.evaluate("""
        var btn = document.querySelector('button[type=submit]') ||
                  document.querySelector('input[type=submit]') ||
                  document.querySelector('button.btn-primary') ||
                  document.querySelector('button');
        if (btn) { btn.click(); console.log('Clicou: ' + btn.innerText); }
        else { console.log('Nenhum botao encontrado'); }
    """)
    page.wait_for_timeout(7000)
    salvar(page, "05_apos_pesquisa")

    sem_resultado = page.locator("text=Nenhum desligamento programado").is_visible()
    print("Sem resultado visivel: " + str(sem_resultado))

    if sem_resultado:
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
            page.screenshot(path="erro.png", full_page=True)
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
