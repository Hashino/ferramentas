#!/usr/bin/env python3
"""Cliente mínimo de LLM grátis (endpoint OpenAI-compatible) para a pipeline.

Chave e modelo NÃO ficam neste repo: são lidos em runtime de ~/.config ou do
.env do learnive (mesmos nomes de variável), que já tem um provider free
configurado e testado. Nenhum segredo entra no git daqui.

Lições herdadas do learnive (ver comentários do .env de lá, vale ouro):
  - free tier tem 429 por POOL do modelo, não por conta: a chave não compra
    orçamento privado. Ao tomar 429, TROCAR de modelo é melhor que esperar.
  - gpt-oss às vezes despeja a resposta no canal `reasoning` em vez de
    `content` (~1/3 das vezes com reasoning_effort default). Por isso aqui
    manda reasoning_effort="low" E faz fallback pro campo reasoning.

Aqui o uso é leve (dezenas de chamadas curtas por leva, ~300 tokens cada),
bem dentro de 30 RPM / 8K TPM — perfil oposto ao do learnive, que estourava.

Uso como módulo:  from ai import perguntar; perguntar("...", json_mode=True)
Uso como teste:   python3 scripts/ai.py
"""
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

# a Groq devolve o tempo de espera dentro da MENSAGEM de erro, não num header
# Retry-After ("Please try again in 3.08s") — TPM (tokens por minuto) é o
# limite que estoura em uso em lote (triagem.py roda dezenas de chamadas
# seguidas), diferente do uso leve original que este cliente foi desenhado
# para. Sem isso, 4 tentativas alternando entre os 2 modelos saturados
# esgotam rápido e o chamador recebe SemIA à toa.
# "Please try again in 3m22.176s" — sem o grupo de minutos a regex antiga não
# casava nada e o cliente dormia os 2s do fallback, queimando as 6 tentativas
# em 12 segundos contra um limite que precisava de 3 minutos (18/09/2026).
_RETRY_APOS = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s", re.I)


def _espera_sugerida(detalhe: str, padrao: float = 2.0) -> float:
    m = _RETRY_APOS.search(detalhe)
    if not m:
        return padrao
    return int(m.group(1) or 0) * 60 + float(m.group(2)) + 0.5

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/129.0.0.0 Safari/537.36")

FONTES_ENV = [
    pathlib.Path(__file__).resolve().parent.parent / ".env",
    pathlib.Path.home() / "Projects" / "learnive" / ".env",
]


def _config() -> dict:
    cfg = {}
    for chave in ("LEARNIVE_API_BASE_URL", "LEARNIVE_API_KEY", "LEARNIVE_MODEL_FAST",
                  "LEARNIVE_MODEL_ROBUST"):
        if os.environ.get(chave):
            cfg[chave] = os.environ[chave]
    for fonte in FONTES_ENV:
        if not fonte.exists():
            continue
        for linha in fonte.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha.startswith("#") or "=" not in linha:
                continue
            k, _, v = linha.partition("=")
            k, v = k.strip(), v.strip()
            if k.startswith("LEARNIVE_") and v and k not in cfg:
                cfg[k] = v
        if "LEARNIVE_API_KEY" in cfg:
            break
    return cfg


class SemIA(RuntimeError):
    """Nenhum provider free disponível agora — o chamador deve seguir sem IA."""


def perguntar(prompt: str, *, sistema: str = "", json_mode: bool = False,
              robusto: bool = False, tentativas: int = 6,
              max_tokens: int = 1500) -> str:
    cfg = _config()
    base = cfg.get("LEARNIVE_API_BASE_URL")
    key = cfg.get("LEARNIVE_API_KEY")
    if not base or not key:
        raise SemIA("sem LEARNIVE_API_BASE_URL/LEARNIVE_API_KEY")

    # ordem de fallback: ao tomar 429 o certo é trocar de modelo, não esperar
    modelos = [cfg.get("LEARNIVE_MODEL_ROBUST"), cfg.get("LEARNIVE_MODEL_FAST")]
    if not robusto:
        modelos.reverse()
    modelos = [m for m in modelos if m]

    if json_mode:
        # a Groq recusa response_format=json_object se a palavra "json" não
        # aparecer em alguma mensagem (400 invalid_request_error)
        sistema = (sistema + "\n" if sistema else "") + "Responda somente com JSON válido."

    msgs = ([{"role": "system", "content": sistema}] if sistema else []) + \
           [{"role": "user", "content": prompt}]

    ultimo = ""
    for i in range(tentativas):
        modelo = modelos[i % len(modelos)]
        corpo = {
            "model": modelo,
            "messages": msgs,
            "temperature": 0,
            "max_tokens": max_tokens,
            "reasoning_effort": "low",  # senão a resposta vaza pro canal reasoning
        }
        if json_mode:
            corpo["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions",
            data=json.dumps(corpo).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                # sem User-Agent de browser o Cloudflare da Groq devolve 403
                # "error code: 1010" (bloqueio de bot) — não é erro de chave.
                "User-Agent": UA,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            txt = (msg.get("content") or "").strip()
            if not txt:  # gpt-oss às vezes responde no canal de raciocínio
                txt = (msg.get("reasoning") or "").strip()
            if txt:
                return txt
            ultimo = "resposta vazia"
        except urllib.error.HTTPError as e:
            try:
                detalhe = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                detalhe = ""
            ultimo = f"{e.code} {e.reason} {detalhe}"
            if e.code == 429:
                # TPD (tokens por dia) é diferente de TPM: o modelo está morto
                # para o resto do dia, insistir nele só gasta tentativa. Sai da
                # lista e a vez passa para o outro modelo.
                if "tokens per day" in detalhe.lower() and len(modelos) > 1:
                    print(f"[ai] {modelo}: cota diária estourada, usando só o outro modelo",
                          file=sys.stderr)
                    modelos = [x for x in modelos if x != modelo]
                    continue
                espera = min(_espera_sugerida(detalhe), 45.0)
                time.sleep(espera)  # e na volta o `i % len` já troca de modelo
                continue
            if e.code in (500, 502, 503):
                time.sleep(1.5)
                continue
            raise SemIA(f"{modelo}: {ultimo}") from e
        except Exception as e:
            ultimo = str(e)
            time.sleep(1.5)
    raise SemIA(f"esgotou {tentativas} tentativas; último erro: {ultimo}")


def perguntar_json(prompt: str, *, sistema: str = "", robusto: bool = False,
                   max_tokens: int = 1500) -> dict:
    txt = perguntar(prompt, sistema=sistema, json_mode=True, robusto=robusto,
                    max_tokens=max_tokens)
    txt = txt.strip()
    if txt.startswith("```"):  # alguns modelos free embrulham em cerca markdown
        txt = txt.split("```")[1].lstrip("json").strip()
    return json.loads(txt)


if __name__ == "__main__":
    cfg = _config()
    print(f"base : {cfg.get('LEARNIVE_API_BASE_URL', '(ausente)')}")
    print(f"chave: {'presente' if cfg.get('LEARNIVE_API_KEY') else 'AUSENTE'}")
    print(f"fast : {cfg.get('LEARNIVE_MODEL_FAST')}  robust: {cfg.get('LEARNIVE_MODEL_ROBUST')}")
    try:
        r = perguntar_json('Responda {"ok": true} e nada mais.')
        print("smoke test:", r)
    except SemIA as e:
        sys.exit(f"IA indisponível: {e}")
