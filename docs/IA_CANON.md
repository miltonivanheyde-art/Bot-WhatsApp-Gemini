# IA_CANON.md - Arquitectura de IA

**Versión: 1.0 (CONGELADO)**

## 🎯 Propósito

- **Fuente de verdad:** Define la arquitectura de IA del proyecto.
- **Regla fundamental:** Solo se consideran válidas las capacidades demostradas mediante ejecución real.
- **Objetivo:** Evitar la reinvestigación de funcionalidades ya validadas.

---

## 🏗️ Arquitectura

### API Actual (Producción)

- **Endpoint:** `client.models.generate_content(...)`
- **Estado:** ✅ Estable, ✅ Validada, ✅ Disponible para producción.

### Arquitectura Objetivo

- **Endpoint:** `client.interactions.create(...)`
- **Estado:** ✅ Validada funcionalmente. Soporta memoria, herramientas y grounding.

---

## 🤖 Modelo Oficial

**Modelo:** `models/gemini-flash-lite-latest`

**Motivos:**

- Mejor relación latencia/calidad.
- Cuotas de uso elevadas.
- Comportamiento consistente en pruebas.

---

## ✅ Capacidades Funcionalmente Validadas

### Interactions API

- **Endpoint:** `client.interactions.create(...)`
- **Estado:** ✅ Funcionamiento básico validado.

### Memoria Conversacional

- **Mecanismo:** `previous_interaction_id`
- **Resultado:** ✅ Recupera contexto entre interacciones (validado con conversación multi-turno).

### Tool Calling

- **Flujo:** Detección de intención → Generación de `ToolCall` → Ejecución local → Devolución de resultados → Síntesis del modelo.
- **Estado:** ✅ Ciclo completo validado.

### Grounding / RAG

- **Mecanismo:** Inyección dinámica de documentos en el `contents` del prompt.
- **Resultado:** ✅ El modelo diferencia correctamente entre conocimiento general y conocimiento inyectado.

---

## 🧪 Formatos de Input Validados (`contents`)

- ✅ `input="texto"` (String simple)
- ✅ `input=["texto"]` (Lista de strings)
- ✅ `types.Content(...)` (Objeto tipado)

---

## 📦 Objeto `Interaction` Validado

**Campos confirmados:** `id`, `output_text`, `previous_interaction_id`, `steps`, `status`, `usage`, `created`, `updated`.

**Corrección Canónica:**

- **Forma incorrecta:** `response.parts[0].text` ❌
- **Forma correcta:** `response.output_text` ✅

---

## 🤖 Agents

### Existencia

- **Endpoint:** `client.agents`
- **Métodos detectados:** `create()`, `get()`, `list()`, `delete()`.
- **Estado:** ✅ API existe.

### Funcionamiento

- **Resultado observado:** Todas las pruebas de creación devolvieron `invalid_request`.
- **Estado:** ❌ No existe creación funcional validada.

---

## 🚫 Capacidades Descartadas

- **Deep Research:** No forma parte de la arquitectura actual. No es una capacidad general de `Interactions`.

---

## 📊 Estado Actual del Proyecto

### Capacidades Validadas

- ✅ Interactions (básico)
- ✅ Memoria Conversacional
- ✅ Tool Calling
- ✅ Grounding / RAG

### Capacidades Pendientes

- ❌ Agents (funcionamiento)

### Fases Completadas

- ✅ Fase 2 – Descubrimiento Tecnológico
- ✅ Fase 3A – Memoria Conversacional
- ✅ Fase 3B/3C – Tool Calling (Trigger y Full Loop)
- ✅ Fase 4A – Grounding / RAG

---

## 🎯 Próximo Objetivo

**Foco:** Agents.

**Tareas:**

1. Validar la creación, recuperación y listado de un Agente.
2. Validar el uso de un Agente mediante `interactions.create(agent=...)`.

---

## 📌 Directiva Operativa

- La fase de descubrimiento se considera cerrada para Memoria, Tools y Grounding.
- El foco del proyecto pasa a **Integración, Consolidación, Implementación y Despliegue**.
- Toda modificación futura de este documento debe estar respaldada por evidencia obtenida mediante ejecución real.
