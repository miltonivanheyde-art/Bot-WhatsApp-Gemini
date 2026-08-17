# INFORME DE ESTADO DEL PROYECTO

**Fecha de la última revisión:** 17 de agosto de 2026
**Análisis realizado por:** Gemini Code Assist
**Fuente de evidencia:** Código fuente del repositorio (`app/main.py`, `app/gemini_service.py`) y ejecución real del sistema.

---

## 1. Resumen Ejecutivo

El proyecto es un bot de WhatsApp implementado en Python con el framework FastAPI. Su arquitectura está diseñada para ser ejecutada localmente, utilizando `ngrok` para exponer un webhook a la API de Meta.

**El bot se encuentra actualmente en un estado plenamente funcional, con la integración de la Inteligencia Artificial de Gemini completamente operativa.** La aplicación procesa los mensajes entrantes de WhatsApp, mantiene el contexto de la conversación (memoria) y genera respuestas dinámicas utilizando la API `Interactions` de Gemini.

Este informe actualiza el estado del proyecto, invalidando las conclusiones de informes anteriores que describían un estado de "mantenimiento" o una falta de implementación de la IA. La arquitectura objetivo definida en `IA_CANON.md` para las capacidades básicas de interacción y memoria ha sido alcanzada y está en producción local.

---

## 2. Estado Actual Observado

El análisis del código fuente (`app/main.py` y `app/gemini_service.py`) y la ejecución real del sistema revelan el siguiente flujo operativo:

- **Recepción de Mensajes:** El webhook en `app/main.py` recibe y procesa correctamente los mensajes de texto de los usuarios de WhatsApp.
- **Gestión de Memoria y Persistencia:** Al iniciar, el sistema carga el estado de las conversaciones desde el archivo `state.json`. Para cada mensaje entrante, se recupera el `previous_interaction_id` asociado al número del remitente, si existe. Este ID se utiliza para mantener la memoria conversacional.
- **Llamada al Servicio de IA:** El mensaje del usuario y el `previous_interaction_id` se pasan a la función `generar_respuesta_gemini` en `app/gemini_service.py`.
- **Generación de Respuesta con Gemini:**
  - `gemini_service.py` carga un prompt de sistema base desde `app/gemini_system_prompt.md`.
  - Se inyecta dinámicamente la fecha actual en el prompt del sistema para proporcionar contexto temporal a la IA.
  - Se realiza una llamada a la API de Gemini utilizando `CLIENT.interactions.create`, que es la arquitectura canónica definida.
  - La llamada incluye el `previous_interaction_id` para asegurar que Gemini mantenga el contexto de la conversación.
- **Actualización y Persistencia del Estado:** La respuesta de Gemini incluye un nuevo `interaction_id`. Este ID se almacena en la memoria del bot asociado al número del remitente y se guarda de forma persistente en `state.json`, asegurando que la memoria sobreviva a reinicios del servidor.
- **Envío de Respuesta:** La respuesta generada por Gemini se envía de vuelta al usuario a través de la API de WhatsApp.

---

## 3. Arquitectura Observada

- **Lenguaje:** Python
- **Framework Web:** FastAPI
- **Servidor de Aplicaciones:** Uvicorn
- **Túnel de Red:** Ngrok (para exponer el servidor local a internet)
- **Dependencias Principales (`requirements.txt`):** `fastapi`, `uvicorn`, `python-dotenv`, `requests`, `ngrok`, `google-genai`.
- **Gestión de Secretos:** El sistema utiliza el paquete `python-dotenv` para cargar variables de entorno (tokens y claves) desde un archivo `bot.env`, que está correctamente excluido del control de versiones mediante `.gitignore`.
- **Persistencia de Estado:** El archivo `state.json` se utiliza para la persistencia del estado de la conversación y también está excluido del control de versiones.

---

## 4. Comportamiento Operacional Observado (Ejecución Real)

La ejecución del bot a través de `iniciar_bot.bat` y la interacción real con usuarios de WhatsApp muestran el siguiente comportamiento:

1. **Al iniciar:**
    - Se activa el entorno virtual.
    - Se muestra la URL pública generada por `ngrok` para el webhook.
    - Se carga el estado de las conversaciones desde `state.json` (o se inicia vacío si no existe).
    - Se carga el prompt del sistema desde `app/gemini_system_prompt.md`.
    - `🔗 URL pública del webhook: https://<id_ngrok>.ngrok-free.app`
    - `✅ Estado cargado desde 'state.json'.`
    - `[PROMPT] System instruction cargada desde: app/gemini_system_prompt.md`
2. **Al verificar el webhook desde Meta:** Se registra un mensaje de éxito.
    - `WEBHOOK VERIFICADO con éxito.`
3. **Al recibir un mensaje de un usuario:**
    - Se registra la recepción del mensaje y el número del remitente.
    - Se invoca a Gemini, mostrando el modelo utilizado.
    - Se registra el `interaction_id` de la nueva interacción.
    - Se envía la respuesta generada por Gemini al usuario.
    - `--- NUEVO WEBHOOK RECIBIDO ---`
    - `Mensaje de <numero_remitente>: '<texto_recibido>'`
    - `🤖 Tita iA`
    - `Modelo: models/gemini-flash-lite-latest`
    - `Interaction: <interaction_id>`
    - `📤 RESPUESTA ENVIADA`
    - `👤 <numero_remitente>`
    - `✅ OK`
4. **Eventos de estado de WhatsApp:** Se registran los estados de los mensajes (Enviado, Entregado, Leído).
    - `📬 Enviado ✔️`
    - `📬 Entregado ✔️✔️`
    - `📬 Leído 👀`

---

## 5. Estado de Integración Gemini

**Estado: ✅ Integración completa y funcional en el flujo principal del bot.**

La integración de las capacidades fundamentales de Gemini en el flujo productivo del bot ha sido finalizada y validada mediante ejecución real.

### Capacidades Integradas en Producción Local

- ✅ **Interactions API:** Es el motor principal de la IA, utilizando `client.interactions.create` para todas las interacciones.
- ✅ **Memoria Conversacional:** Implementada y persistente a través de `previous_interaction_id` y el almacenamiento en `state.json`.
- ✅ **Prompt Dinámico:** El prompt de sistema se carga desde `app/gemini_system_prompt.md` y se enriquece con datos dinámicos (fecha actual) antes de cada llamada a la IA.
- ✅ **Persistencia de Estado:** El estado de la conversación (los `interaction_id` por usuario) se guarda y carga de `state.json`, asegurando que la memoria sobreviva a reinicios del servidor.

### Capacidades Validadas (Pendientes de Integración en el Flujo Principal)

- ⚠️ **Tool Calling (Full Loop):** La capacidad de Tool Calling ha sido validada funcionalmente en entornos de prueba (como se detalla en `IA_CANON.md`), pero aún no está integrada en el flujo principal del bot para su uso en WhatsApp.
- ⚠️ **Grounding / RAG:** La capacidad de inyección de documentos (RAG) ha sido validada funcionalmente, pero aún no está integrada en el flujo principal del bot.

### Capacidades Pendientes de Validación Funcional

- ⚠️ **Agents:** La API `client.agents` existe, pero su creación y funcionamiento no han sido validados con éxito. La investigación sobre `Agents` sigue en suspenso.
- ⚠️ **Investigación ANSES:** Existe una línea de investigación sobre adquisición y estructuración de conocimiento ANSES. Actualmente se encuentra en fase exploratoria. Las herramientas locales de crawling, scraping y extracción documental no forman parte de la arquitectura oficial del sistema y no deben considerarse componentes validados.

---

## 6. Estado Git Observable

- **Configuración (`.gitignore`):** El archivo está correctamente configurado para excluir del repositorio el entorno virtual, la caché de Python y, crucialmente, los archivos de secretos (`bot.env`, `.env`) y de estado (`state.json`).
- **Ramas y Commits:** El estado de la rama actual, el historial de commits y la existencia de tags no son verificables desde el contexto de análisis de archivos. La `doctrina.md` prescribe el uso de la rama `feature/integracion-gemini` para el trabajo de desarrollo.

---

## 7. Riesgos Actuales

1. **Discrepancia Documental:** Aunque este informe busca corregirla, la documentación histórica (`PROJECT_STATUS.md` e `IA_CANON.md` en sus versiones anteriores) contenía información obsoleta que podría generar confusión si no se actualiza formalmente.
2. **Incertidumbre del Baseline:** La `doctrina.md` menciona un baseline funcional (`whatsapp-baseline-funcional`), pero su existencia y validez no pueden ser verificadas directamente desde el contexto de archivos, lo que podría comprometer una estrategia de rollback si no se gestiona adecuadamente.
3. **Escalabilidad de Persistencia:** La persistencia actual mediante `state.json` es adecuada para el estado operativo actual del proyecto. Requerimientos futuros de escalabilidad deberán evaluarse cuando exista evidencia concreta que lo justifique.

---

## 8. Roadmap Definido por Doctrina

El plan de acción obligatorio para la integración de Gemini, definido en `doctrina.md`, ha sido completado en su totalidad para las funcionalidades básicas de interacción y memoria.

- **Objetivo:** Implementar la IA de Gemini para generar respuestas dinámicas.
- **Plan de Etapas (Estado Actual):**
    1. **Etapa 1 (Módulo Aislado):** ✅ Completada. Se creó `app/gemini_service.py`.
    2. **Etapa 2 (Prueba Aislada):** ✅ Completada. Se validó la conexión y funcionalidad de Gemini de forma independiente.
    3. **Etapa 3 (Validación Aislada):** ✅ Completada. Se confirmó que el servicio de IA funciona correctamente.
    4. **Etapa 4 (Integración Mínima):** ✅ Completada. Se conectó el servicio Gemini al webhook en `app/main.py`.
    5. **Etapa 5 (Fallback):** ✅ Completada. El bloque `try...except` en `gemini_service.py` maneja errores de Gemini y devuelve una respuesta controlada.
    6. **Etapa 6 (Prueba Real):** ✅ Completada. El flujo completo de extremo a extremo ha sido validado desde un teléfono.

  ### Nota de Estado

    Las etapas de validación tecnológica originalmente previstas fueron ejecutadas mediante la auditoría Gemini y se consideran materialmente completadas. La siguiente fase ya no es validación tecnológica básica sino la integración de capacidades avanzadas y la evolución del sistema.

---

## 9. Dictamen Final del Proyecto

La fase de integración inicial de Gemini se declara formalmente **concluida y exitosa**. La viabilidad técnica de la arquitectura objetivo ha sido demostrada mediante la ejecución real y el bot es funcional.

### Estado General del Proyecto

- **Código productivo:** ✅ **Funcional y con IA integrada.**
- **Arquitectura objetivo:** ✅ **Implementada y en uso.**
- **Conocimiento técnico:** ✅ Consolidado en `IA_CANON.md` (una vez actualizado).
- **Documentación:** ⚠️ **Atrasada** (este informe y la actualización de `IA_CANON.md` corrigen esta discrepancia).

### Nueva Directiva Operativa

La prioridad del proyecto pasa de la integración básica a la **evolución de capacidades y la mejora continua**. Las capacidades de `Tool Calling` y `Grounding` fueron validadas funcionalmente y permanecen disponibles para futuras decisiones de integración. La investigación sobre `Agents` y la integración de conocimiento específico (como el de ANSES) son otras líneas de trabajo posibles.

---

## 10. Estado de la Capa de Conocimiento Verificable

**Estado General:**

- **Arquitectura:** ✅ APROBADA (Diseño V3.1 documentado en `docs/KNOWLEDGE_LAYER_DESIGN.md`).
- **Implementación:** Autorizada por fases.
- **Validación Funcional:** ⚠️ PENDIENTE.

### Fase A: Especificación Arquitectónica

- **Estado:** ✅ COMPLETADA.
- **Evidencia:** Creación del documento `docs/KNOWLEDGE_LAYER_DESIGN.md`.

### Fase B: Esquema y Acceso SQLite Aislado

- **Estado:** ✅ IMPLEMENTADA Y VALIDADA DE FORMA AISLADA.
- **Evidencia:**
  - Creación de `app/database.py` con el esquema versionado de SQLite.
  - Creación de `tests/test_database.py` para validación unitaria.
  - Ejecución de 17 pruebas unitarias con resultado `OK`.
  - `python -m py_compile` finalizó sin errores.
  - `git diff --check` finalizó sin errores.
- **Commits:**
  - `a755d9d`: Implementación inicial de la Fase B mediante app/database.py y tests/test_database.py.
  - `36d2e83`: Corrección de robustez y validación final de la Fase B.
- **Estado del Repositorio (post-Fase B):**
  - **Rama:** `feature/integracion-gemini`.
  - Cambios sincronizados con el repositorio remoto.
  - Árbol de trabajo limpio (`working tree clean`) después del `push`.

### Fase C: Recuperación Puntual Aislada

*   **Estado:** ✅ IMPLEMENTADA Y VALIDADA DE FORMA AISLADA.
*   **Evidencia (proporcionada por el usuario):**
    *   `app/web_retrieval_service.py` creado.
    *   `tests/test_web_retrieval.py` creado.
    *   Compilación de sintaxis finalizó sin errores.
    *   20 pruebas unitarias del recuperador web ejecutadas con resultado `OK`.
    *   17 pruebas de regresión de la capa de base de datos (SQLite) ejecutadas con resultado `OK`.
    *   `git diff --check` finalizó sin errores.
*   **Commit:** `cc46537`
*   **Estado del Repositorio (post-Fase C):**
    *   **Rama:** `feature/knowledge-web-retrieval`.
    *   Cambios publicados en el repositorio remoto.
    *   Árbol de trabajo limpio (`working tree clean`) después del `push`.

**Capacidades Implementadas Aisladamente:**
-   HTTPS obligatorio.
-   Dominios permitidos: `anses.gob.ar` y `argentina.gob.ar`, incluidos subdominios.
-   Manejo manual de hasta 3 redirecciones, con validación de seguridad en cada paso.
-   Validación de todas las direcciones IPv4 e IPv6 devueltas por `getaddrinfo`.
-   Bloqueo de direcciones IP no globales (privadas, loopback, etc.) para mitigar SSRF.
-   Límites de tamaño de contenido (10 MB) y tipos MIME.
-   Descarga incremental de contenido.
-   Cálculo de hash SHA-256.
-   Manejo de errores controlado mediante excepciones personalizadas.

### Aclaraciones Obligatorias sobre el Estado Actual

- **Integración con el Bot:** ❌ No existe integración con `app/main.py`.
- **Integración con IA:** ❌ No existe integración con `app/gemini_service.py`.
- **Integración con Base de Datos:** ❌ No existe integración entre `web_retrieval_service` y `database.py`.
- **Recuperación Web:** ✅ `app/web_retrieval_service.py` está implementado y validado de forma aislada, pero no está integrado ni habilitado para uso productivo.
- **Servicio de Conocimiento:** ❌ No se ha implementado `app/knowledge_service.py`.
- **Validación Humana:** ❌ No existe la herramienta de validación humana.
- **Base de Datos:** ⚠️ El archivo `data/tita.db` (si existe) es para desarrollo y no constituye una base de conocimiento poblada o productiva.
- **Validación:** ❌ No se realizaron pruebas con acceso a internet real. El módulo no tiene uso productivo.
- **Riesgos y Funcionalidad Pendiente:** ⚠️ La correspondencia temática queda pendiente. Permanece documentado el riesgo de DNS rebinding/TOCTOU. La Capa de Conocimiento Verificable completa todavía no está validada funcionalmente.
