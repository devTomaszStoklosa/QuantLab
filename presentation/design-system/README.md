# QuantForge — design system

Źródła design systemu warstwy prezentacji (rozszerzenie `q7-dotnet-react-presentation`). Opublikowana wersja: https://claude.ai/artifact/XC5niEQ9L256sNFsx5FSB4 (prywatna; udostępnienie z menu Share).

Zgodnie z [ADR-0006](../../docs/adr/0006-dotnet-react-presentation-layer-only.md) to wyłącznie warstwa prezentacji: komponenty dostają liczby policzone przez `quantlab` i tylko je formatują — nie liczą żadnych metryk.

## Zawartość

| Ścieżka | Co |
|---|---|
| `project/README.md` | brand book: zasady, ton, liczby, kolory, typografia, ikony, wykresy (po angielsku — język UI produktu) |
| `project/guidelines/10-experience.md` | architektura informacji, kluczowe ekrany, reguły interakcji |
| `project/tokens.json` | tokeny: dwa motywy (Paper / Graphite), typografia, odstępy, promienie, cienie |
| `project/components/bundle.js`, `bundle.css`, `index.d.ts` | 31 komponentów React 18 jako `window.QuantForge` + typy |
| `project/components/<Nazwa>/` | wytyczne (`README.md`) i podgląd (`preview.html`) każdego komponentu; `*Screen` to pełne ekrany |
| `project/components/lib/` | React 18.3.1 (licencja MIT, nagłówki licencji w plikach) |
| `project/assets/Logos/` | znak w wersji na jasne i ciemne tło |
| `project/design-system.json` | indeks artefaktu Design System |
| `tools/` | generatory i test renderowania |

Dane na ekranach są syntetyczne (deterministyczne ziarno), nie są wynikami badań.

Aplikacja `presentation/web` używa tych plików bezpośrednio: `bundle.js` i `bundle.css` importuje po ustawieniu `window.React`, a zmienne CSS tokenów generuje z `tokens.json` (to samo mapowanie co `tools/build_test.py`).

## Regeneracja i sprawdzenie

```bash
cd presentation/design-system
python tools/make_tokens.py project/tokens.json   # tokeny + raport kontrastu (musi być "fails: 0")
python tools/make_previews.py                     # preview.html wszystkich komponentów i ekranów
python tools/make_docs.py                         # README komponentów
python tools/build_test.py                        # składa strony testowe do test/
node tools/shot.js $(cd test && ls *.html)        # zrzuty do shots/ + błędy konsoli (wymaga Playwright)
```

`Cover/preview.html`, `bundle.js`, `bundle.css`, `index.d.ts` i `project/README.md` są edytowane ręcznie. Katalogi `test/` i `shots/` są ignorowane przez git.
