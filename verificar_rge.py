import os, sys, base64, json, requests
from datetime import datetime, timedelta

DIAS_FRENTE = 5
ID_MUNICIPIO = "711"
BAIRRO = "Industrial"
URL_API = "https://spir.cpfl.com.br/api/ConsultaDesligamentoProgramado/Pesquisar"
URL_SITE = "https://spir.cpfl.com.br/Publico/ConsultaDesligamentoProgramado/Visualizar/4"

def formatar_data(dt):
    return dt.strftime("%d/%m/%Y")

def consultar():
    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)

    params = {
        "PeriodoDesligamentoInicial": formatar_data(hoje),
        "PeriodoDesligamentoFinal": formatar_data(fim),
        "IdMunicipio": ID_MUNICIPIO,
        "NomeBairro": BAIRRO,
        "NomeRua": "",
    }

    headers = {
        "Referer": URL_SITE,
        "User-Agent": "Mozilla/5.0",
    }

    print("Consultando API...")
    print("Periodo: " + formatar_data(hoje) + " ate " + formatar_data(fim))

    resp = requests.get(URL_API, params=params, headers=headers, timeout=20)
    print("Status HTTP: " + str(resp.status_code))

    dados = resp.json()

    resultado = []
    for municipio in dados.get("Data", []):
        for data_item in municipio.get("Datas", []):
            data = data_item["Data"][:10]
            for doc in data_item.get("Documentos", []):
                for bairro in doc.get("Bairros", []):
                    ruas = ", ".join([ru["NomeRua"] for ru in bairro.get("Ruas", [])])
                    resultado.append({
                        "Data": data,
                        "Horario": doc["PeriodoExecucaoInicial"][11:16] + " ate " + doc["PeriodoExecucaoPeriodoFinal"][11:16],
                        "Documento": doc["DescricaoDocumento"],
                        "Motivo": doc["NecessidadeDocumento"],
                        "Bairro": bairro["NomeBairro"],
                        "Ruas": ruas,
                    })
    return resultado

def main():
    try:
        desligamentos = consultar()
    except Exception as e:
        print("Erro: " + str(e))
        sys.exit(1)

    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)
    periodo = formatar_data(hoje) + " ate " + formatar_data(fim)

    if not desligamentos:
        print("Nenhum desligamento encontrado.")
        corpo = "Nenhum desligamento em Sao Marcos - Industrial. Periodo: " + periodo
        tem_alerta = False
    else:
        print("ALERTA: " + str(len(desligamentos)) + " desligamento(s) encontrado(s)!")
        linhas = ["ALERTA: " + str(len(desligamentos)) + " desligamento(s) em Sao Marcos - Bairro Industrial"]
        linhas.append("Periodo verificado: " + periodo)
        linhas.append("")
        for i, d in enumerate(desligamentos, 1):
            linhas.append("Desligamento " + str(i) + ":")
            for k, v in d.items():
                linhas.append("  " + k + ": " + str(v))
            linhas.append("")
        linhas.append("Consulte em: " + URL_SITE)
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
