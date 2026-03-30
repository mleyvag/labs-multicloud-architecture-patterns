# MOD3-LAB3: Arquitectura Orientada a Eventos en Google Cloud
**Instructor:** Miguel Leyva

---

## 1. Objetivo, alcance
**Objetivo**
* El objetivo de este laboratorio es implementar una arquitectura desacoplada utilizando el patrón de diseño Publisher/Subscriber (Pub/Sub) en Google Cloud Platform.
* El estudiante configurará un sistema de mensajería asíncrona donde un evento disparado manualmente activa una función sin servidor.

**Qué aprenderá el alumno**
* Crear y gestionar Tópicos y Suscripciones en Google Cloud Pub/Sub.
* Desplegar lógica de negocio en Cloud Functions (2nd Gen).
* Implementar Eventarc para conectar servicios de forma asíncrona.
* Monitorear la ejecución de eventos mediante Cloud Logging.

---

## 2. Prerrequisitos y herramientas
* Una cuenta activa de Google Cloud Platform (GCP).
* Un proyecto de GCP seleccionado con facturación (Billing) habilitada.
* Permisos de rol Owner o Editor sobre el proyecto.

---

## 3. El Problema

Usted es el Arquitecto de Soluciones para "ShopUTEC", una plataforma de comercio electrónico en crecimiento. Actualmente, el sistema procesa las órdenes de compra de manera monolítica.
* Cuando un cliente hace clic en "Comprar", el sistema web intenta cobrar, actualizar el inventario y enviar un correo de confirmación en una sola secuencia síncrona.
* Si el servicio de correo falla, la transacción completa se cancela, causando pérdida de ventas y una mala experiencia de usuario.

### La Solución
Implementar una arquitectura Event-Driven. La web publicará un mensaje "Nueva Orden" en un bus de eventos y un microservicio independiente procesará la orden en segundo plano.

---

## 4. Arquitectura y decisiones de diseño
### Descripción
La arquitectura consta de tres componentes principales desacoplados por un bus de mensajes.
* **Publisher (Simulado):** La consola de GCP actuará como el frontend, enviando un payload JSON.
* **Broker (Pub/Sub):** Actúa como intermediario. Recibe mensajes y garantiza su entrega.
    * **Decisión de Diseño:** Se elige Pub/Sub por ser un servicio global, serverless y capaz de manejar picos de tráfico sin aprovisionamiento previo.
* **Consumer (Cloud Functions):** Función `procesador-ordenes`.
    * **Decisión de Diseño:** Se utiliza FaaS (Function as a Service) para pagar solo por ejecución, ideal para cargas de trabajo basadas en eventos esporádicos.

---

## 5. Laboratorio guiado (Paso a paso)
### FASE 1: Preparación del Entorno (APIs)
1. Ingrese a la consola: https://console.cloud.google.com/
2. En la barra de búsqueda superior, escriba: Cloud Resource Manager API.
3. Haga clic en **Habilitar** (Enable) si no está activa.
4. Repita el proceso para las siguientes APIs:
    * Cloud Pub/Sub API
    * Cloud Functions API
    * Eventarc API
    * Artifact Registry API

### FASE 2: Crear el Canal de Mensajería (Pub/Sub)
1. En el menú de navegación, vaya a **Pub/Sub** > **Temas** (Topics).
2. Haga clic en el botón superior **CREAR TEMA** (CREATE TOPIC).
3. Complete los campos:
    * **ID del tema:** `ordenes-compra`
    * **Agregar una suscripción predeterminada:** [ ] Desmarcar.
    * **Usar un esquema:** [ ] Desmarcar.
4. Haga clic en **CREAR**.

### FASE 3: Desplegar el Procesador (Cloud Function)
1. Busque y seleccione el servicio **Cloud Functions**.
2. Haga clic en **CREAR FUNCIÓN**.
3. **Sección Configuración:**
    * **Entorno:** Seleccione **2nd gen**.
    * **Nombre de la función:** `procesador-ordenes`.
    * **Región:** `us-central1`.
4. **Sección Activador (Trigger):**
    * Haga clic para editar el activador (por defecto HTTPS).
    * Seleccione tipo: **Cloud Pub/Sub**.
    * En "Seleccionar un tema", elija: `projects/.../topics/ordenes-compra`.
    * Haga clic en **GUARDAR EVENTO**.
5. Haga clic en **SIGUIENTE**.

### FASE 4: Codificación
1. **Configuración del Runtime:**
    * **Tiempo de ejecución:** Node.js 20.
    * **Punto de entrada:** `helloPubSub`.
2. **Código Fuente (index.js):** Reemplace todo el contenido con el siguiente código:

```javascript
const functions = require('@google-cloud/functions-framework');

functions.cloudEvent('helloPubSub', (cloudEvent) => {
  // El mensaje real viene codificado en base64
  const base64String = cloudEvent.data.message.data;
  // Decodificamos el mensaje a texto plano
  const jsonString = Buffer.from(base64String, 'base64').toString();
  
  console.log(`⚡ EVENTO RECIBIDO!`);
  console.log(`📦 ID del Mensaje: ${cloudEvent.id}`);
  
  try {
      const orden = JSON.parse(jsonString);
      console.log(`✅ Orden Procesada para cliente: ${orden.cliente}`);
      console.log(`💰 Total de la orden: $${orden.total}`);
  } catch (e) {
      console.log("⚠️ Mensaje recibido (No JSON): " + jsonString);
  }
});
```

3. Haga clic en **IMPLEMENTAR** (DEPLOY). Espere unos minutos hasta ver el check verde.

---

## 6. Pruebas y validación
### Pasos de Validación
1. Vaya a **Pub/Sub** > **Temas**.
2. Haga clic sobre el ID `ordenes-compra`.
3. Vaya a la pestaña **MENSAJES** > **PUBLICAR MENSAJE**.
4. En el cuerpo del mensaje, ingrese el siguiente JSON:

```json
{
  "id_orden": "ORD-5599",
  "cliente": "Estudiante UTEC",
  "items": ["Laptop", "Mouse"],
  "total": 1500
}
```

5. Haga clic en **PUBLICAR**.

### Resultado Esperado
* Vaya a **Cloud Functions** > `procesador-ordenes` > pestaña **LOGS**.
* Debería visualizar: `✅ Orden Procesada para cliente: Estudiante UTEC`.
* Esto confirma que el flujo asíncrono funciona.

---

## 7. Cambio de escenario (nuevos requerimientos)
### Nuevos Requerimientos Funcionales
* El departamento de Marketing ha solicitado una funcionalidad crítica: Detección de clientes VIP.
* Cada vez que entra una orden mayor a $1000, se debe notificar a un sistema paralelo para enviar un cupón de descuento.

### Impacto en la Arquitectura
* En un sistema monolítico, tendríamos que editar el código principal, arriesgando la estabilidad del procesamiento de pagos.
* En nuestra arquitectura Event-Driven, aplicaremos el patrón Fan-Out:
    * No modificaremos la función `procesador-ordenes`.
    * Agregaremos un nuevo suscriptor al mismo tema.
* **Impacto de Costos:** Se duplicará el número de invocaciones de funciones por cada mensaje, pero no afectará la latencia del usuario final.

---

## 8. Laboratorio propuesto (reto)
### El Reto
Implemente el requerimiento de Marketing sin interrumpir el servicio actual.

### Instrucciones
1. Cree una segunda Cloud Function llamada `marketing-vip`.
2. Utilice el mismo trigger (Pub/Sub) apuntando al tema `ordenes-compra`.
3. Modifique el código para incluir una condicional `if`:
    * Si `total > 1000`: Imprimir `"🎯 CLIENTE VIP DETECTADO - ENVIAR CUPÓN"`.
    * Si no: No hacer nada.
4. Realice una prueba enviando un solo mensaje a Pub/Sub.

### Resultado de éxito
Al publicar un solo mensaje, deberá ver logs activos en ambas funciones simultáneamente.

---

## 9. Preguntas, conclusiones y aprendizajes
### Preguntas de Reflexión
* **Resiliencia:** Si la función de `marketing-vip` falla por un error de sintaxis, ¿afecta esto a la función `procesador-ordenes`? *(R: No, son procesos aislados).*
* **Idempotencia:** ¿Qué pasaría si Pub/Sub entrega el mismo mensaje dos veces por error de red? ¿Nuestro código está preparado para no cobrar doble?

### Conclusiones
* Hemos logrado desacoplar la generación del evento de su procesamiento.
* La arquitectura permite agregar nuevas funcionalidades (Marketing) sin tocar el código existente (Open/Closed Principle).
* Cloud Functions escala automáticamente a cero, optimizando costos cuando no hay ventas.

---

## 10. Limpieza y consideraciones de costo
### Pasos de Limpieza (Obligatorio)
Para evitar cargos inesperados por almacenamiento de imágenes o recursos huérfanos:

**Eliminar Funciones:**
1. Servicio: **Cloud Functions**.
2. Seleccione `procesador-ordenes` y `marketing-vip`.
3. Clic en **ELIMINAR**.

**Eliminar Tópico:**
1. Servicio: **Pub/Sub** > **Temas**.
2. Seleccione `ordenes-compra`.
3. Clic en **ELIMINAR**.

**Eliminar Imágenes de Contenedor:**
1. Servicio: **Artifact Registry**.
2. Seleccione los repositorios creados (ej. `us-central1-docker.pkg.dev...`).
3. Elimine las imágenes dentro para liberar espacio de almacenamiento.

**Estimación de costo:** Si deja estos recursos activos 24h sin tráfico, el costo es cercano a $0.00 USD gracias a la capa gratuita, pero el almacenamiento de Artifact Registry podría generar centavos a fin de mes.