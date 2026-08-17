# DISEÑO DE CAPA DE CONOCIMIENTO VERIFICABLE

**Versión:** 3.1
**Estado:** ARQUITECTURA APROBADA | FASES B Y C IMPLEMENTADAS Y VALIDADAS AISLADAMENTE | INTEGRACIÓN FUNCIONAL PENDIENTE

## 1. Estado y Alcance

Este documento define la arquitectura para una **Capa de Conocimiento Verificable**. Su objetivo es permitir que el bot Tita responda consultas institucionales utilizando una base de datos local, poblada con información recuperada de manera controlada desde fuentes oficiales y validada por humanos.

Esta propuesta ha sido aprobada. Los componentes de las Fases B (`app/database.py`) y C (`app/web_retrieval_service.py`) están implementados y validados aisladamente. Los demás componentes y la integración funcional completa continúan pendientes.

## 2. Principios de Seguridad y Confianza

1. **Verdad Única:** La base de conocimiento `VALIDATED` es la única fuente de verdad para respuestas institucionales.
2. **Cero Confianza en Contenido No Validado:** El contenido `PENDING`, `STALE` o `REJECTED` nunca debe ser presentado como un hecho.
3. **Fallback Restringido:** La IA generativa (Gemini) no puede inventar información institucional. Su rol es conversacional y de orientación cuando no existe conocimiento `VALIDATED`.
4. **Minimización de Datos:** La recopilación y almacenamiento de datos, tanto de fuentes como de consultas de usuario, se limitará al mínimo indispensable.
5. **Trazabilidad Total:** Cada pieza de conocimiento y cada decisión de validación debe ser auditable, desde su origen hasta su uso.

---

## 3. Arquitectura y Responsabilidades

### Componentes Arquitectónicos

* **`app/database.py` (Propuesta)**
  * **Responsabilidad:** Abstraer y gestionar todas las interacciones con la base de datos SQLite. Provee una API interna para operaciones CRUD, inicialización del esquema y gestión de transacciones. Es el único módulo que interactúa directamente con el archivo de la base de datos.

* **`app/knowledge_service.py` (Propuesta)**
  * **Responsabilidad:** Orquestar el ciclo de vida del conocimiento. Recibe consultas, determina la estrategia de respuesta (búsqueda local o recuperación web), procesa los resultados y gestiona el almacenamiento de nuevas versiones de conocimiento para su posterior validación. No contiene lógica de acceso a la web ni a la base de datos directamente.

* **`app/web_retrieval_service.py` (Propuesta)**
  * **Responsabilidad:** **Servicio de recuperación puntual de información oficial para una consulta concreta.**
  * **Prohibiciones:** No es un scraper generalizado, crawler, indexador ni recolector masivo. No recorre sitios completos, no indexa dominios, no sigue enlaces indiscriminadamente y no recupera contenido sin una consulta u objetivo explícito. No almacena contenido procedente de búsquedas generales sin verificar su URL final.
  * **Dominios Autorizados:** `anses.gob.ar`, `argentina.gob.ar`.
  * **Clasificación de Fuente:** La clasificación (`official` / `non_official`) se realiza utilizando el hostname efectivo de la URL final, después de resolver todas las redirecciones HTTP (3xx).

* **`data/tita.db` (Propuesta)**
  * **Responsabilidad:** Archivo de base de datos SQLite que contiene el conocimiento institucional, el historial de versiones, los registros de validación y los logs de consulta.

* **Herramienta de Validación Humana (Propuesta Futura)**
  * **Responsabilidad:** Interfaz (CLI o web) externa al bot que permite a los revisores humanos autorizados examinar las entradas `PENDING` y `STALE`, compararlas con sus fuentes originales y actualizar su estado a `VALIDATED` o `REJECTED`.

---

## 4. Modelo de Datos Versionado

El modelo de datos está diseñado para ser versionado, permitiendo la auditoría y la gestión de cambios en el tiempo.

### Justificación de Tablas

* **`sources`**: Representa una URL canónica de origen.
* **`knowledge_versions`**: Registra cada captura de contenido de una `source` en un momento dado, incluyendo su estado actual de validación.
* **`validations`**: Es un log histórico de todas las decisiones de validación (eventos) sobre una `knowledge_version`.
* **`knowledge_entries`**: Representa una unidad semántica de conocimiento (ej. "Requisitos AUH"). Apunta a la `knowledge_version` que actualmente la representa como `VALIDATED`.
* **`form_identities`**: Representa la identidad estable de un formulario (ej. "PS 1.47 - Libreta AUH").
* **`form_versions`**: Vincula una `form_identity` a una `knowledge_version` específica que contiene el documento del formulario.
* **`query_logs`**: Proporciona trazabilidad operativa con un enfoque en la privacidad.

### Esquema SQLite Conceptual

```sql
-- Tabla: sources
-- Almacena las URLs canónicas de las fuentes de información.
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_url TEXT NOT NULL UNIQUE, -- URL de referencia para la fuente
    source_domain TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('official', 'non_official', 'unknown'))
);

CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources (source_domain);

-- Tabla: knowledge_versions
-- Registra cada captura de contenido de una fuente en un momento específico, incluyendo su estado actual.
CREATE TABLE IF NOT EXISTS knowledge_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    final_url TEXT NOT NULL, -- URL efectiva después de redirecciones
    retrieval_date TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    original_content BLOB NOT NULL, -- Contenido binario o texto crudo
    extracted_text TEXT, -- Texto limpio y procesado para búsqueda/RAG
    content_type TEXT NOT NULL CHECK(content_type IN ('formulario', 'pagina', 'pdf', 'tramite', 'faq', 'calendario', 'instructivo', 'otro')),
    http_status_code INTEGER NOT NULL,
    mime_type TEXT,
    current_status TEXT NOT NULL CHECK(current_status IN ('PENDING', 'VALIDATED', 'REJECTED', 'STALE')), -- Estado actual de esta versión
    current_validated_by TEXT, -- Último validador
    current_validation_date TEXT, -- Fecha de la última actualización de estado
    UNIQUE(source_id, content_hash), -- Una fuente no debe tener el mismo contenido dos veces
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_versions_hash ON knowledge_versions (content_hash);
CREATE INDEX IF NOT EXISTS idx_knowledge_versions_status ON knowledge_versions (current_status);

-- Tabla: validations
-- Log histórico de todas las decisiones de validación sobre las versiones de conocimiento.
CREATE TABLE IF NOT EXISTS validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    validation_event_type TEXT NOT NULL CHECK(validation_event_type IN ('SUBMITTED_FOR_VALIDATION', 'VALIDATED_EVENT', 'REJECTED_EVENT', 'STALED_EVENT', 'REVALIDATED_EVENT')),
    event_by TEXT,
    event_date TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (version_id) REFERENCES knowledge_versions(id)
);

-- Tabla: knowledge_entries
-- Representa una unidad semántica de conocimiento (ej. "Requisitos AUH").
-- Apunta a la knowledge_version que actualmente la representa como VALIDATED.
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL UNIQUE, -- Título descriptivo del concepto de conocimiento
    keywords TEXT, -- Palabras clave para búsqueda
    description TEXT, -- Descripción breve del conocimiento
    active_version_id INTEGER, -- FK a knowledge_versions (debe ser VALIDATED)
    FOREIGN KEY (active_version_id) REFERENCES knowledge_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_entries_title ON knowledge_entries (title);
CREATE INDEX IF NOT EXISTS idx_knowledge_entries_keywords ON knowledge_entries (keywords);

-- Tabla: form_identities
-- Representa la identidad estable de un formulario (ej. "PS 1.47 - Libreta AUH").
CREATE TABLE IF NOT EXISTS form_identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_code TEXT NOT NULL UNIQUE, -- ej. "PS 1.47"
    form_name TEXT NOT NULL,
    organism TEXT NOT NULL -- ej. "ANSES"
);

-- Tabla: form_versions
-- Vincula una identidad de formulario a una versión específica de conocimiento (el documento PDF o página).
CREATE TABLE IF NOT EXISTS form_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_identity_id INTEGER NOT NULL,
    knowledge_version_id INTEGER NOT NULL UNIQUE, -- Cada versión de formulario apunta a una única knowledge_version
    detected_version TEXT, -- Versión del formulario si se informa en el documento (ej. "2023-05")
    official_date TEXT, -- Fecha oficial del formulario si se informa en el documento (ISO 8601)
    FOREIGN KEY (form_identity_id) REFERENCES form_identities(id),
    FOREIGN KEY (knowledge_version_id) REFERENCES knowledge_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_form_versions_identity ON form_versions (form_identity_id);

-- Tabla: query_logs
-- Registra las consultas operativas con minimización de datos.
CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL, -- ID de sesión seudonimizado.
    timestamp TEXT NOT NULL,
    response_type TEXT NOT NULL CHECK(response_type IN ('VALIDATED_KNOWLEDGE', 'PENDING_NOTICE', 'STALE_NOTICE', 'GEMINI_FALLBACK', 'ERROR')),
    used_knowledge_entry_id INTEGER, -- FK a knowledge_entries si se usó conocimiento validado
    FOREIGN KEY (used_knowledge_entry_id) REFERENCES knowledge_entries(id)
);
```

### Estados y Transiciones

* **`PENDING`**: Estado inicial de toda nueva `knowledge_version` recuperada.
* **`VALIDATED`**: Aprobado por un revisor humano. Es el único estado utilizable para respuestas institucionales.
* **`REJECTED`**: Rechazado por un revisor humano. No se utiliza.
* **`STALE`**: Anteriormente `VALIDATED`, pero una nueva versión del mismo `source` ha sido recuperada, o ha pasado un tiempo definido sin re-verificación. No se utiliza para respuestas directas.

**Transiciones Permitidas (en `knowledge_versions.current_status`):**

* `[NUEVO]` → `PENDING` (Automático por `knowledge_service` al recuperar)
* `PENDING` → `VALIDATED` (Manual por revisor)
* `PENDING` → `REJECTED` (Manual por revisor)
* `VALIDATED` → `STALE` (Automático por sistema al detectar nueva versión o por tiempo)
* `STALE` → `VALIDATED` (Manual por revisor tras re-validación)
* `STALE` → `REJECTED` (Manual por revisor)
* `REJECTED` → `PENDING` (Manual por revisor si se decide re-evaluar)

---

## 5. Flujo Operativo y Manejo de Estados

### Recuperación Puntual y Validación Técnica Mínima

Antes de que `knowledge_service` cree una entrada en `knowledge_versions` con estado `PENDING`, `web_retrieval_service` debe confirmar:

1. URL válida y resolución DNS correcta.
2. Seguimiento de redirecciones (HTTP 3xx) y obtención de la `final_url`.
3. Clasificación del `source_type` (`official`/`non_official`) basado en el hostname de la `final_url`.
4. Respuesta HTTP satisfactoria (2xx).
5. Identificación del `Content-Type` y `MIME-Type` desde las cabeceras.
6. Cálculo del hash (SHA256) del contenido binario recibido.
7. Registro de la fecha y hora de recuperación.
8. Verificación de que la URL no contiene credenciales o datos sensibles.
9. **Correspondencia Temática Mínima:** Realizar una comprobación básica de palabras clave entre la consulta original y el contenido recuperado (ej. en `title` o primeros párrafos) para asegurar una relevancia mínima antes de registrarlo como `PENDING`.

### Búsqueda Local

1. **Entrada:** Consulta del usuario.
2. **Normalización:** La consulta y los campos de búsqueda (`knowledge_entries.title`, `knowledge_entries.keywords`, `knowledge_versions.extracted_text`, `form_identities.form_code`, `form_identities.form_name`) se normalizan (minúsculas, sin acentos, sin espacios extra).
3. **Consulta:** Se buscan `knowledge_entries` que apunten a una `knowledge_version` con `current_status = 'VALIDATED'`.
4. **Criterio:** Se priorizan coincidencias exactas en `form_code` o `title`, luego por `keywords`, y finalmente por búsqueda de texto completo en `extracted_text`.
5. **Resultado:** Si se encuentra una o más `knowledge_entries` de alta confianza, se devuelve la `knowledge_entry` más relevante (y su `active_version_id` asociado). Si no hay coincidencia confiable, se considera un fallo de búsqueda.

### Fallback Restringido y Respuestas Seguras

* **Consulta Ambigua:** Gemini pide aclaraciones.
* **Sin Resultado Local y Recuperación Fallida:** "En este momento no tengo información validada sobre tu consulta y no pude encontrar una fuente oficial para verificar. Te recomiendo visitar directamente anses.gob.ar."
* **Fuente `PENDING` Técnicamente Segura:** "Encontré una posible fuente de información en el sitio oficial, pero su contenido aún no ha sido verificado por nuestro equipo. Para evitar darte información incorrecta, te recomiendo consultar el enlace directamente para tu propia evaluación: [URL de la `final_url` de la `knowledge_version` PENDING]"
* **Fuente `PENDING` Insegura (ej. dominio no oficial, error técnico, baja correspondencia temática):** Se trata como "Recuperación Fallida". No se muestra la URL.
* **Información `STALE`:** "Tengo información sobre tu consulta, pero podría estar desactualizada. La última versión validada es del [current_validation_date de la `knowledge_version` STALE]. Para evitar darte información incorrecta, te recomiendo verificar la información en la fuente oficial: [URL de la `final_url` de la `knowledge_version` STALE]" **El contenido factual de la versión `STALE` nunca se proporciona.**
* **Error Interno:** "Ocurrió un error al procesar tu solicitud. Por favor, intenta de nuevo más tarde."

---

## 6. Validación Humana

El procedimiento de validación humana es un control de calidad no automatizable:

1. El revisor selecciona una `knowledge_version` con `current_status = 'PENDING'` o `STALE` desde la herramienta de validación.
2. Comprueba la `final_url` de la `knowledge_version` y la `retrieval_date`.
3. Verifica que el `source_type` (`official`) sea correcto.
4. Compara el `original_content` con la fuente en vivo para asegurar fidelidad.
5. Valida que el `extracted_text` es una extracción fiel, sin interpretaciones.
6. Confirma que el `content_type` es adecuado.
7. Si es un formulario, verifica y registra los metadatos en `form_identities` y `form_versions`.
8. Registra un nuevo evento en la tabla `validations` con la decisión (`VALIDATED_EVENT` o `REJECTED_EVENT`), su identificador, la fecha y notas si es necesario.
9. Actualiza el `current_status` de la `knowledge_version` a `VALIDATED` o `REJECTED`.
10. Si el estado es `VALIDATED`, se crea o actualiza la `knowledge_entry` correspondiente, apuntando a esta `knowledge_version` como `active_version_id`.

---

## 7. Privacidad y Trazabilidad (Query Logs)

* **Seudonimización:** El `user_id` (número de WhatsApp) no se almacenará. Se usará un `session_id` seudonimizado (ej. un hash del `user_id` con una sal rotativa) para agrupar consultas de una misma conversación sin identificar al usuario. **El algoritmo de seudonimización es una decisión pendiente.**
* **Contenido:** No se almacenará el texto de la consulta (`query_text`) a menos que sea explícitamente necesario para análisis de "misses" y con una política de retención estricta. No se almacenarán las respuestas completas de Gemini.
* **Política de Retención (Propuesta):** Los `query_logs` se conservarán por un período limitado (ej. 90 días) para análisis operativo y luego serán eliminados o agregados de forma anónima. **Esta política requiere aprobación.**

---

## 8. Relación Futura con Grounding y Tool Calling

* **Grounding/RAG:** El `extracted_text` de una o más `knowledge_versions` vinculadas a `knowledge_entries` con estado `VALIDATED` podrá ser inyectado en el prompt de Gemini para que genere una respuesta conversacional basada en hechos verificados. La respuesta final deberá incluir la `final_url` de la fuente como referencia.
* **Tool Calling:** `knowledge_service` podrá ser expuesto como una herramienta (`search_validated_knowledge(query: str)`). Gemini podrá invocar esta herramienta para obtener datos fácticos `VALIDATED` y usarlos para construir su respuesta. En ningún caso una herramienta devolverá contenido que no sea `VALIDATED`.

Ambas integraciones requerirán una fase de implementación y validación independiente y no forman parte de esta propuesta inicial.

---

## 9. Fases Futuras de Implementación

La implementación de esta capa se propone en las siguientes fases atómicas:

* **Fase A: Especificación Arquitectónica.**
  * **Objetivo:** Completar el diseño detallado de la capa de conocimiento.
  * **Archivos Previstos:** `docs/KNOWLEDGE_LAYER_DESIGN.md`.
  * **Componentes Protegidos:** Todo el código existente del bot.
  * **Dependencias:** Ninguna nueva.
  * **Evidencia Requerida:** Documento de diseño aprobado.
  * **Riesgo:** Bajo.
  * **Validación:** Revisión documental.
  * **Rollback:** Descartar el documento.
  * **Criterios de Aceptación:** Documento completo, consistente y aprobado por la dirección técnica.

* **Fase B: Esquema y Acceso SQLite Aislado.**
  * **Objetivo:** Crear `app/database.py` y validar la creación del esquema y las operaciones CRUD básicas para todas las tablas.
  * **Archivos Previstos:** `app/database.py`, `tests/test_database.py` (nuevo).
  * **Componentes Protegidos:** `app/main.py`, `app/gemini_service.py`, `state.json`.
  * **Dependencias:** `sqlite3` (built-in).
  * **Evidencia Requerida:** Pruebas unitarias exitosas de creación de tablas e inserción/recuperación de datos.
  * **Riesgo:** Bajo.
  * **Validación:** Ejecución de `tests/test_database.py`.
  * **Rollback:** Eliminar `app/database.py` y `tests/test_database.py`.
  * **Criterios de Aceptación:** `app/database.py` funcional y probado de forma aislada.

* **Fase C: Recuperación Puntual Aislada.**
  * **Estado:** ✅ COMPLETADA (Implementación y validación aislada).
  * **Objetivo:** Crear `app/web_retrieval_service.py` y validarlo con pruebas unitarias que demuestren la recuperación de contenido, manejo de redirecciones, clasificación de fuentes y validación técnica mínima desde dominios permitidos.
  * **Archivos Previstos:** `app/web_retrieval_service.py`, `tests/test_web_retrieval.py` (nuevo).
  * **Componentes Protegidos:** `app/main.py`, `app/gemini_service.py`, `app/database.py`.
  * **Dependencias:** `requests`, `beautifulsoup4`, `lxml` (ya existentes).
  * **Evidencia Requerida:** Pruebas unitarias exitosas cubriendo escenarios de éxito, fallo, redirecciones y clasificación de dominios.
  * **Riesgo:** Medio (depende de la estabilidad de los sitios externos).
  * **Validación:** Ejecución de `tests/test_web_retrieval.py`.
  * **Rollback:** Eliminar `app/web_retrieval_service.py` y `tests/test_web_retrieval.py`.
  * **Criterios de Aceptación:** `app/web_retrieval_service.py` funcional y probado de forma aislada.

* **Fase D: Servicio de Conocimiento Aislado.**
  * **Objetivo:** Crear `app/knowledge_service.py` y probar su lógica de orquestación (búsqueda, decisión de recuperación, almacenamiento `PENDING`) utilizando mocks para `database` y `web_retrieval`.
  * **Archivos Previstos:** `app/knowledge_service.py`, `tests/test_knowledge_service.py` (nuevo).
  * **Componentes Protegidos:** `app/main.py`, `app/gemini_service.py`.
  * **Dependencias:** `app/database.py`, `app/web_retrieval_service.py` (vía mocks).
  * **Evidencia Requerida:** Pruebas unitarias exitosas que validen los flujos de decisión y el manejo de estados `PENDING`.
  * **Riesgo:** Bajo.
  * **Validación:** Ejecución de `tests/test_knowledge_service.py`.
  * **Rollback:** Eliminar `app/knowledge_service.py` y `tests/test_knowledge_service.py`.
  * **Criterios de Aceptación:** `app/knowledge_service.py` funcional y probado de forma aislada.

* **Fase E: Herramienta de Revisión Humana.**
  * **Objetivo:** Desarrollar una herramienta CLI o web mínima para que un humano pueda cambiar el estado de las entradas de `PENDING` a `VALIDATED`/`REJECTED`/`STALE` y gestionar `knowledge_entries` y `forms`.
  * **Archivos Previstos:** `tools/knowledge_validator.py` (nuevo).
  * **Componentes Protegidos:** Todo el bot.
  * **Dependencias:** `app/database.py`.
  * **Evidencia Requerida:** Demostración manual de la herramienta, actualizando estados en `data/tita.db`.
  * **Riesgo:** Bajo.
  * **Validación:** Pruebas manuales de la interfaz.
  * **Rollback:** Eliminar `tools/knowledge_validator.py`.
  * **Criterios de Aceptación:** Herramienta funcional para la gestión de estados de conocimiento.

* **Fase F: Integración Mínima con el Bot.**
  * **Objetivo:** Modificar `app/main.py` para que llame a `knowledge_service` y maneje los diferentes tipos de respuesta definidos (conocimiento validado, aviso de pendiente, fallback a Gemini).
  * **Archivos Previstos:** `app/main.py`.
  * **Componentes Protegidos:** `app/gemini_service.py`, `state.json`.
  * **Dependencias:** `app/knowledge_service.py`.
  * **Evidencia Requerida:** Pruebas funcionales desde WhatsApp cubriendo los flujos básicos de respuesta.
  * **Riesgo:** Medio (impacto en el flujo principal del bot).
  * **Validación:** Pruebas de integración de extremo a extremo desde un teléfono.
  * **Rollback:** Revertir cambios en `app/main.py`.
  * **Criterios de Aceptación:** Bot responde correctamente según la lógica de `knowledge_service`.

* **Fase G: Validación Funcional Completa.**
  * **Objetivo:** Realizar pruebas de extremo a extremo desde WhatsApp, cubriendo todos los escenarios de respuesta definidos (incluyendo `STALE`, `PENDING` seguro/inseguro, `VALIDATED`, fallback).
  * **Archivos Previstos:** Ninguno nuevo, solo ejecución.
  * **Componentes Protegidos:** Todos.
  * **Dependencias:** Todos los componentes de la capa de conocimiento y el bot.
  * **Evidencia Requerida:** Informe de pruebas detallado con capturas de pantalla/logs de todos los escenarios.
  * **Riesgo:** Bajo (fase de prueba).
  * **Validación:** Ejecución exhaustiva de casos de prueba.
  * **Rollback:** Si se encuentran errores, revertir a la fase F o anterior.
  * **Criterios de Aceptación:** Todos los escenarios de respuesta funcionan como se espera.

* **Fase H: Evaluación Separada de Grounding/RAG.**
  * **Objetivo:** Una vez que la capa de conocimiento es estable, iniciar una nueva fase para integrar el conocimiento `VALIDATED` en el contexto de Gemini mediante Grounding/RAG.
  * **Archivos Previstos:** `app/gemini_service.py`, `app/main.py`.
  * **Componentes Protegidos:** `app/database.py`, `app/knowledge_service.py`.
  * **Dependencias:** `google-genai` SDK.
  * **Evidencia Requerida:** Pruebas funcionales que demuestren que Gemini utiliza el contexto `VALIDATED` para generar respuestas.
  * **Riesgo:** Medio (impacto en la calidad de la respuesta de Gemini).
  * **Validación:** Pruebas de integración y evaluación de la calidad de las respuestas.
  * **Rollback:** Revertir cambios en `app/gemini_service.py` y `app/main.py`.
  * **Criterios de Aceptación:** Gemini genera respuestas precisas y contextualizadas usando el conocimiento `VALIDATED`.

* **Fase I: Evaluación Separada de Tool Calling.**
  * **Objetivo:** Integrar `knowledge_service` como una herramienta para Gemini, permitiendo que Gemini decida cuándo consultar la base de conocimiento.
  * **Archivos Previstos:** `app/gemini_service.py`, `app/main.py`.
  * **Componentes Protegidos:** `app/database.py`, `app/knowledge_service.py`.
  * **Dependencias:** `google-genai` SDK.
  * **Evidencia Requerida:** Pruebas funcionales que demuestren que Gemini invoca la herramienta de conocimiento y usa sus resultados.
  * **Riesgo:** Medio (complejidad de la orquestación de Gemini).
  * **Validación:** Pruebas de integración y evaluación del comportamiento de Gemini.
  * **Rollback:** Revertir cambios en `app/gemini_service.py` y `app/main.py`.
  * **Criterios de Aceptación:** Gemini utiliza la herramienta de conocimiento de forma autónoma y efectiva.

---

## 10. Decisiones que Requieren Aprobación Antes de Implementar

1. **Algoritmo de Seudonimización:** Definir el algoritmo y la gestión de la sal para el `session_id` en `query_logs`.
2. **Política de Retención de Logs:** Aprobar el período de retención final para los `query_logs` y el procedimiento de eliminación/agregación.
3. **Diseño de la Herramienta de Validación:** Especificar los requerimientos funcionales para la herramienta de revisión humana (CLI vs. Web, autenticación, interfaz de usuario, etc.).
4. **Estrategia de Búsqueda Local:** Aprobar el mecanismo de búsqueda inicial (ej. SQLite FTS5 vs. `LIKE` con normalización manual) y los umbrales de confianza para considerar una coincidencia suficiente.
5. **Criterios para `STALE`:** Definir las reglas exactas para que una entrada `VALIDATED` pase a `STALE` (ej. tiempo transcurrido sin re-verificación, detección de cambio en la fuente).
6. **Manejo de `original_content`:** Decidir si `original_content` se almacena como `TEXT` (para HTML/texto) o `BLOB` (para PDFs) y cómo se gestiona la extracción de texto para `extracted_text` en cada caso.
