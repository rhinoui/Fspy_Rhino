# Dependencies

This project has **no pip-installable dependencies**.

All required modules are either part of the Python standard library or bundled with Rhino:

| Module | Source | Purpose |
|---|---|---|
| `json` | Python stdlib | Parse fSpy JSON files |
| `math` | Python stdlib | Trigonometry for FOV / focal length conversion |
| `os` | Python stdlib | File extension check |
| `Rhino` | Rhino SDK | Document, viewport, geometry, named views |
| `System.Drawing` | .NET / Rhino | `System.Drawing.Size` for render resolution |
| `Eto.Forms` | Rhino UI framework | File dialog and message boxes |

## Runtime

- **Rhino 6+** with IronPython (included)
- No CPython or external packages needed
