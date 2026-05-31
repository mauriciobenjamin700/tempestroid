# Instalação

## Desenvolvimento (este repositório)

O fluxo de desenvolvimento usa [uv](https://docs.astral.sh/uv/). Um único comando
instala o núcleo, o ferramental e o simulador Qt:

```bash
uv sync        # núcleo + ferramental de dev + simulador Qt
```

Isso instala, além das dependências de runtime:

- o grupo de dev (`ruff`, `pyright`, `pytest`, `pytest-asyncio`);
- o simulador Qt (`PySide6`, `qasync`) — faz parte do loop de dev/teste;
- o site de documentação (`mkdocs-material`).

## Usuários finais

Quem só vai consumir o framework instala via `pip`. O **núcleo** depende apenas
de `pydantic`; o Qt é um extra opcional:

```bash
pip install tempestroid          # apenas o núcleo (precisa só de pydantic)
pip install "tempestroid[qt]"    # com o simulador de desktop (PySide6 + qasync)
```

## Documentação

O site de documentação (este conteúdo) é construído com MkDocs Material, instalado
pelo `uv sync`:

```bash
uv run mkdocs serve              # servidor local com hot reload em http://127.0.0.1:8000
uv run mkdocs build --strict     # build de produção; falha em qualquer aviso
```

## Pré-requisitos por alvo

| Alvo | Precisa de |
|---|---|
| Simulador Qt (desktop) | Python ≥ 3.11 + extra `qt` (`PySide6`/`qasync`). |
| Dispositivo Android | Android SDK/NDK + a árvore `android-host/` (Trilho B). Não roda sem o toolchain. |

!!! warning "Trilho B (Android) precisa do toolchain"
    Empacotar e rodar no dispositivo exige Android SDK/NDK e a árvore
    `android-host/`. Veja a [pesquisa de runtime Android](research/android-runtime.md)
    e o [runbook](research/android-runbook.md).
