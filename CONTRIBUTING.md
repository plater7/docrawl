# Contribuir a Docrawl

¡Gracias por tu interés en contribuir a Docrawl!

## Primeros pasos

1. Haz un fork del repositorio
2. Clona tu fork: `git clone https://github.com/<tu-usuario>/docrawl.git`
3. Crea una rama: `git checkout -b feat/mi-feature`
4. Instala dependencias: `pip install -r requirements.txt`
5. (Opcional) Instala Playwright para pruebas de integración: `playwright install chromium`

## Setup de desarrollo

```bash
# Ejecutar localmente
uvicorn src.main:app --host 0.0.0.0 --port 8002 --reload

# Ejecutar con Docker
docker compose up --build

# Ejecutar tests
pytest --cov=src --cov-report=term-missing
```

### Pre-commit hooks

El proyecto usa [pre-commit](https://pre-commit.com/) con `ruff` para linting y formato:

```bash
pip install pre-commit
pre-commit install
# Verificar todos los archivos manualmente:
pre-commit run --all-files
```

## Conventional Commits

Todos los commits deben seguir la convención [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>(scope opcional): <descripción corta>
```

### Tipos permitidos

| Tipo | Cuándo usarlo |
|------|---------------|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `docs` | Solo cambios de documentación |
| `chore` | Tareas de mantenimiento, deps, CI |
| `refactor` | Refactoring sin cambio de comportamiento |
| `test` | Añadir o corregir tests |
| `perf` | Mejora de rendimiento |

### Ejemplos

```
feat(crawler): add sitemap index support
fix(llm): handle timeout in chunk cleanup
docs(readme): add multi-provider configuration section
chore(ci): remove unnecessary Playwright install in test workflow
test(filter): add tests for language variant filtering
```

### Reglas

- Descripción en **inglés**, en imperativo, sin punto final
- Máximo 72 caracteres en la primera línea
- `BREAKING CHANGE:` en el body si el cambio rompe compatibilidad
- Referencias a issues: `Closes #123` al final del body

## Estándares de código

- **Python 3.12** con type hints
- **async/await** para todo I/O
- **Pydantic** para validación de datos
- Usar módulo `logging`, nunca `print()`
- Simplicidad: sin abstracciones innecesarias

## Proceso de Pull Request

1. Asegúrate de que los tests pasan: `pytest`
2. Verifica linting: `ruff check src/ tests/`
3. Verifica formato: `ruff format --check src/ tests/`
4. Actualiza la documentación si es necesario
5. Completa el template del PR
6. Solicita revisión a `@plater7`

## Reportar issues

- **Bugs**: Usa el template de Bug Report
- **Features**: Usa el template de Feature Request
- **Seguridad**: Ver [SECURITY.md](SECURITY.md) para disclosure responsable

## Código de conducta

Sé respetuoso. Escribe mensajes de commit claros. Mantén los PRs enfocados y pequeños.
