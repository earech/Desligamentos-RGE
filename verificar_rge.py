import os, sys, base64, json
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

DIAS_FRENTE = 5
URL = "https://spir.cpfl.com.br/Publico/ConsultaDesligamentoProgramado/Visualizar/4"

def formatar_data(dt):
    return dt.strftime("%d/%m/%Y")

def salvar(page, nome):
    page.screenshot(path=nome + ".png", full_page=True)
    print("Salvo: " + nome)

def consultar(page):
    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)

    respostas = []

    def capturar_resposta(response):
        url = response.url
        if "Pesquisar" in url or "desligamento" in url.lower() or "consulta" in url.lower():
            print("Interceptado: " + url + " status:" + str(response.status))
            try:
                respostas.append({"url": url, "body": response.text()})
            except Exception as ex:
                print("Erro ao ler resposta: " + str(ex))

    def capturar_request(request):
        if request.method == "POST":
            print("POST: " + request.url)
            print("POST body: " + str(request.post_data)[:500])

    page.on("response", capturar_resposta)
    page.on("request", capturar_request)

    print("Carregando pagina...")
    page.goto(URL, wait_until="networkidle", timeout=40000)
    page.wait_for_timeout(3000)
    salvar(page, "01_inicial")

    print("Preenchendo e submetendo...")
    page.evaluate("""
        var radio = document.getElementById('TipoConsulta_Localizacao');
        if (radio) {
            radio.checked = true;
            radio.dispatchEvent(new Event('change', {bubbles:true}));
        }
        var inputs = document.querySelectorAll('input[type=text]');
        if (inputs[0]) { inputs[0].value = '""" + formatar_data(hoje) + """'; inputs[0].dispatchEvent(new Event('change', {bubbles:true})); }
        if (inputs[1]) { inputs[1].value = '""" + formatar_data(fim) + """'; inputs[1].dispatchEvent(new Event('change', {bubbles:true})); }
        var sel = document.getElementById('IdMunicipio');
        if (sel) {
            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].text.indexOf('Marcos') !== -1) {
                    sel.selectedIndex = i;
                    sel.dispatchEvent(new Event('change', {bubbles:true}));
                    break;
                }
            }
        }
        var bairro = document.getElementById('Bairro');
        if (bairro) { bairro.value = 'Industrial'; bairro.dispatchEvent(new Event('change', {bubbles:true})); }
        var btn = document.querySelector('button[type=submit]') || document.querySelector('button');
        if (btn) btn.click();
    """)

    page.wait_for_timeout(8000)
    salvar(page, "02_apos_submit")

    print("Requisicoes POST capturadas: " + str(len(respostas)))
    for r in respostas:
        print("URL: " + r["url"])
        print("Body: " + str(r["body"])[:2000])

    if not respostas:
        print("Nenhuma requisicao AJAX capturada - verificando pagina...")
        print(page.locator("body").inner_text()[:2000])
        return []

    # Processa a resposta capturada
    for r in respostas:
        try:
            dados = json.loads(r["body"])
            if isinstance(dados, list):
                return dados
            for chave in dados:
                if isinstance(dados[chave], list):
                    return dados[chave]
        except Exception:
            if "Nenhum desligamento" in str(r["body"]):
                return []

    return []

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
            if isinstance(d, dict):
                for k, v in d.items():
                    linhas.append("  " + str(k) + ": " + str(v))
            else:
                linhas.append("  " + str(d))
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
