import os, sys, base64, json
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

DIAS_FRENTE = 5
URL = "https://spir.cpfl.com.br/Publico/ConsultaDesligamentoProgramado/Visualizar/4"

def formatar_data(dt):
    return dt.strftime("%d/%m/%Y")

def consultar(page):
    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)

    ajax_respostas = []

    def capturar(response):
        url = response.url
        if "Pesquisar" in url or "pesquisar" in url or "Desligamento" in url:
            print("AJAX capturado: " + url)
            try:
                ajax_respostas.append(response.text())
            except:
                pass

    page.on("response", capturar)

    print("Carregando pagina...")
    page.goto(URL, wait_until="networkidle", timeout=40000)
    page.wait_for_timeout(3000)

    print("Ativando radio via iCheck/jQuery...")
    page.evaluate("""
        if (typeof $ !== 'undefined') {
            $('#TipoConsulta_Localizacao').iCheck('check');
            console.log('iCheck check chamado');
        } else {
            console.log('jQuery nao disponivel');
        }
    """)
    page.wait_for_timeout(2000)

    print("Preenchendo datas via datepicker...")
    page.evaluate("""
        try {
            $('input[name=from]').datepicker('setDate', '""" + formatar_data(hoje) + """');
            $('input[name=to]').datepicker('setDate', '""" + formatar_data(fim) + """');
            console.log('Datas preenchidas via datepicker');
        } catch(e) {
            console.log('datepicker falhou: ' + e);
            var inputs = document.querySelectorAll('input[type=text]');
            inputs[0].value = '""" + formatar_data(hoje) + """';
            inputs[1].value = '""" + formatar_data(fim) + """';
        }
    """)
    page.wait_for_timeout(500)

    print("Selecionando municipio...")
    page.evaluate("""
        var sel = document.getElementById('IdMunicipio');
        for (var i = 0; i < sel.options.length; i++) {
            if (sel.options[i].text.indexOf('Marcos') !== -1) {
                sel.selectedIndex = i;
                $(sel).trigger('change');
                console.log('Municipio: ' + sel.options[i].text + ' value: ' + sel.options[i].value);
                break;
            }
        }
    """)
    page.wait_for_timeout(500)

    print("Preenchendo bairro...")
    page.evaluate("""
        var b = document.getElementById('Bairro');
        b.value = 'Industrial';
        $(b).trigger('change');
    """)
    page.wait_for_timeout(500)

    print("Clicando pesquisar via jQuery...")
    page.evaluate("""
        var btn = $('button[type=submit]').first();
        if (btn.length) {
            btn.click();
            console.log('Click via jQuery ok');
        } else {
            console.log('Botao nao encontrado');
        }
    """)

    print("Aguardando resposta AJAX...")
    page.wait_for_timeout(10000)

    for r in ajax_respostas:
        if "Nenhum desligamento" in r:
            return []
        try:
            dados = json.loads(r)
            if "Data" in dados:
                resultado = []
                for municipio in dados["Data"]:
                    for data_item in municipio.get("Datas", []):
                        data = data_item["Data"][:10]
                        for doc in data_item.get("Documentos", []):
                            for bairro in doc.get("Bairros", []):
                                ruas = ", ".join([ru["NomeRua"] for ru in bairro.get("Ruas", [])])
                                resultado.append({
                                    "Data": data,
                                    "Documento": doc["DescricaoDocumento"],
                                    "Inicio": doc["PeriodoExecucaoInicial"][11:16],
                                    "Fim": doc["PeriodoExecucaoPeriodoFinal"][11:16],
                                    "Bairro": bairro["NomeBairro"],
                                    "Ruas": ruas,
                                    "Motivo": doc["NecessidadeDocumento"],
                                })
                return resultado
        except Exception as ex:
            print("Erro parse: " + str(ex))

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
