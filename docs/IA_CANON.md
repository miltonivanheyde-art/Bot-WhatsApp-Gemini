# IA_CANON.md - Arquitectura de IA

**Versión: 1.2 (ACTUALIZADO)**

## 🎯 Propósito

- **Fuente de verdad:** Define la arquitectura de IA del proyecto.
- **Regla fundamental:** Solo se consideran válidas las capacidades demostradas mediante ejecución real.
- **Objetivo:** Evitar la reinvestigación de funcionalidades ya validadas.
- **Trazabilidad:** Documenta la evolución de la arquitectura de IA y las decisiones clave.

---

## 🏗️ Arquitectura

### Arquitectura Implementada (Producción Local)

- **Endpoint:** `client.interactions.create(...)`
- **Estado:** ✅ **Implementada y funcional.** Es el endpoint principal utilizado por el bot de WhatsApp para todas las interacciones con Gemini.
- **Capacidades Soportadas:** Soporta memoria conversacional, y está diseñada para integrar herramientas (Tool Calling) y contextualización (Grounding/RAG) en futuras fases.
- **Persistencia de Memoria:** La memoria conversacional se gestiona mediante el `previous_interaction_id` y se persiste en un archivo `state.json` asociado al ID del usuario.

---

## 🤖 Modelo Oficial

**Modelo:** `models/gemini-flash-lite-latest`

**Motivos:**

- Mejor relación latencia/calidad para interacciones conversacionales.
- Cuotas de uso elevadas, adecuadas para un bot de mensajería.
- Comportamiento consistente y predecible en pruebas y ejecución real.

---

## ✅ Capacidades Funcionalmente Validadas

Esta sección describe las capacidades que han sido probadas y confirmadas como técnicamente viables con la API de Gemini.

### Interactions API

- **Endpoint:** `client.interactions.create(...)`
- **Estado:** ✅ **Funcionamiento básico validado y actualmente implementado en producción local.** Permite enviar un prompt y recibir una respuesta del modelo, manteniendo el contexto de la conversación.

### Memoria Conversacional

- **Mecanismo:** Utilización del parámetro `previous_interaction_id` en las llamadas a `client.interactions.create(...)`.
- **Resultado:** ✅ **Recupera contexto entre interacciones (validado con conversación multi-turno) y actualmente implementado en producción local.** El modelo es capaz de recordar y referenciar información de turnos anteriores de la misma conversación.

### Prompt Dinámico

- **Origen:** `app/gemini_system_prompt.md`
- **Estado:** ✅ **Integrado.**
- **Resultado:** ✅ **Utilizado en todas las interacciones de producción local.**

### Contexto Temporal Dinámico

- **Mecanismo:** Sustitución dinámica de `{current_date}`.
- **Estado:** ✅ **Integrado.**
- **Resultado:** ✅ **Fecha actual inyectada en cada interacción.**
- **Evidencia:** Validado mediante ejecución real y logs operativos.

### Tool Calling

- **Flujo:** Detección de intención → Generación de `ToolCall` → Ejecución local → Devolución de resultados → Síntesis del modelo.
- **Estado:** ✅ **Ciclo completo validado funcionalmente en entorno de pruebas.** Se ha demostrado que Gemini puede identificar la necesidad de usar una herramienta, generar la llamada correcta, procesar el resultado de la ejecución de la herramienta y sintetizar una respuesta coherente.
- **Estado de Integración:** ⚠️ **Pendiente de integración en el flujo principal del bot.**

### Grounding / RAG (Retrieval Augmented Generation)

- **Mecanismo:** Inyección dinámica de documentos (o fragmentos de texto) en el `contents` del prompt para proporcionar contexto adicional al modelo.
- **Resultado:** ✅ **El modelo diferencia correctamente entre conocimiento general y conocimiento inyectado (validado funcionalmente en entorno de pruebas).** Permite al modelo responder preguntas basadas en información específica proporcionada, reduciendo alucinaciones.
- **Estado de Integración:** ⚠️ **Pendiente de integración en el flujo principal del bot.**

---

## 🧪 Formatos de Input Validados (`contents`)

Los siguientes formatos han sido probados y confirmados como aceptados por la API de Gemini:

- ✅ `input="texto"` (String simple)
- ✅ `input=["texto"]` (Lista de strings)
- ✅ `types.Content(...)` (Objeto tipado)

---

## 📦 Objeto `Interaction` Validado

**Campos confirmados:** `id`, `output_text`, `previous_interaction_id`, `steps`, `status`, `usage`, `created`, `updated`.

**Corrección Canónica para Extracción de Respuesta:**

- **Forma incorrecta (observada en pruebas iniciales):** `response.parts[0].text` ❌
- **Forma correcta (y actualmente implementada):** `response.output_text` ✅

---

## 🤖 Agents

### Existencia de la API

- **Endpoint:** `client.agents`
- **Métodos detectados:** `create()`, `get()`, `list()`, `delete()`.
- **Estado:** ✅ La API para gestionar Agents existe y es accesible.

### Funcionamiento (Creación y Uso)

- **Resultado observado:** Todas las pruebas de creación de Agents devolvieron `invalid_request`.
- **Estado:** ❌ **No existe creación funcional validada.** La capacidad de crear y utilizar Agents de forma efectiva sigue siendo una incógnita y requiere más investigación o una actualización de la API por parte de Google.

---

## 🚫 Capacidades Descartadas

- **Deep Research:** No forma parte de la arquitectura actual ni de las capacidades directas de `Interactions`. Cualquier necesidad de investigación profunda debe ser gestionada externamente.

---

## 📊 Estado Actual del Proyecto (Resumen de Capacidades de IA)

### Capacidades de IA Integradas en Producción Local

- ✅ Interactions (básico)
- ✅ Memoria Conversacional
- ✅ Prompt Dinámico
- ✅ Contexto Temporal Dinámico
- ✅ Persistencia de Estado

### Capacidades Validadas Pendientes de Integración

- ⚠️ **Tool Calling (validado):** La capacidad de ejecutar herramientas externas está validada pero no integrada en el flujo principal.
- ⚠️ **Grounding / RAG (validado):** La capacidad de inyectar conocimiento externo está validada pero no integrada en el flujo principal.
- ❌ **Agents (no validado):** La capacidad de crear y utilizar agentes no ha sido validada funcionalmente.

### Fases Completadas (Relacionadas con IA)

- ✅ Fase 2 – Descubrimiento Tecnológico (Validación de Interactions, Memoria, Tool Calling, Grounding)
- ✅ Fase 3A – Memoria Conversacional (Integración en el bot)
- ✅ Fase 3B/3C – Tool Calling (Validación, no integración)
- ✅ Fase 4A – Grounding / RAG (Validación, no integración)
- ✅ Integración de `client.interactions.create` en el flujo principal del bot.

---

## 📌 Directiva Operativa

- **Estado de Integración:** La fase de integración inicial (Memoria y `Interactions` básicas) se considera **concluida**.
- **Regla de Evidencia:** Toda modificación futura de este documento debe estar respaldada por evidencia obtenida mediante ejecución real.
- **Regla de No Reinvestigación:** Las capacidades validadas y documentadas en este archivo no deben ser reinvestigadas, salvo que exista evidencia contradictoria o cambios significativos en la API subyacente.
