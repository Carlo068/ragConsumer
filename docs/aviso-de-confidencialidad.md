# Aviso de confidencialidad: qué sale del servidor cuando se usa un asistente de IA

Para la dirección del despacho, antes de iniciar el piloto. No es asesoría legal: los
puntos de la sección 4 deben confirmarse con quien lleve la ética profesional y la
protección de datos del despacho.

## En una frase

Los documentos se guardan en el servidor del despacho, pero **cuando el asistente de IA de
un abogado hace una búsqueda, el texto que encuentra se envía a la empresa que ofrece ese
asistente** (Anthropic, OpenAI u otra). Este sistema no puede impedirlo ni controlar lo
que esa empresa hace con él.

## 1. Qué sale del servidor y a dónde va

Siempre y solo cuando el asistente de un abogado con una llave de acceso válida pregunta:

| Herramienta del asistente | Lo que recibe (y por tanto el proveedor de IA) |
|---|---|
| Buscar | Hasta 5 fragmentos de texto de los documentos que coinciden, cada uno con el nombre del asunto y del archivo |
| Leer un pasaje | El texto completo de ese fragmento |
| Leer un documento | El texto completo de **todo el documento** |
| Listar archivos | Los nombres de los archivos y su estado, en los asuntos que el abogado activó |

Además, el proveedor recibe lo que el propio abogado escribe en su conversación.

**Va a:** el proveedor del asistente que el abogado usa, bajo la cuenta de ese abogado con
el proveedor. La conversación (incluidos esos fragmentos) puede quedar guardada en su
historial de esa cuenta.

**No sale:** el archivo original (PDF, Word, correo), los documentos de asuntos que el
abogado no activó o a los que no tiene acceso, ni el contenido de las bases de datos. El
sistema nunca envía nada por iniciativa propia.

## 2. Lo que el sistema controla y lo que no

| El sistema sí controla | El sistema no puede controlar |
|---|---|
| Que cada persona solo alcance los asuntos a los que pertenece **y** que activó para su IA (se vuelve a comprobar en cada consulta) | Qué hace el proveedor de IA con el texto que recibe: cuánto tiempo lo conserva, si lo usa para entrenar modelos, quién de su personal puede verlo, en qué país lo procesa |
| Retirar el acceso de inmediato (quitar a una persona de un asunto, apagar el interruptor, revocar su llave) | Lo que ya se envió antes de retirar el acceso |
| Registrar cada búsqueda y lectura de la IA: quién, cuándo, en qué asunto y **qué se preguntó**. El administrador puede consultarlo y el registro no se puede alterar (como contiene el texto de las preguntas, también es información confidencial: limite quién es administrador) | Si el abogado copia o pega texto por su cuenta en otra herramienta |

## 3. Recomendaciones

1. **Elija y pague un plan para empresas** (o acceso por API) que garantice por contrato
   que los datos **no se usan para entrenar** modelos y, de preferencia, que se conservan
   **cero días** o el mínimo posible («retención cero»). Los planes gratuitos o personales
   normalmente no lo ofrecen. Pida y archive el contrato o acuerdo de tratamiento de datos.
2. Use **cuentas del despacho**, administradas por él, con verificación en dos pasos. No
   cuentas personales.
3. Si el proveedor lo permite, desactive el **historial de conversaciones y la memoria**.
4. **Active la IA solo en los asuntos donde haga falta**, y apáguela al cerrarlos. Los
   asuntos especialmente delicados, o de clientes que lo prohíban, no deben activarse.
5. Confirme **dónde** procesa el proveedor los datos (país), por si el despacho o sus
   clientes exigen que no salgan de México (ver `docs/deployment/01-provider-options.md`).
6. Revise los términos del proveedor cada vez que cambien, y quién tiene el contrato.
7. Capacite a las personas usuarias (`docs/guia-de-usuario.md`, sección 7).

## 4. Consentimiento del cliente y deberes profesionales (a confirmar con asesoría)

Enviar información de un cliente a un tercero para que la procese puede tocar varias
obligaciones del despacho. Lo que hay que confirmar:

- **Secreto profesional y deber de confidencialidad** frente al cliente, y las normas de
  ética del colegio o barra a la que pertenezcan las personas abogadas.
- **Cláusulas de confidencialidad de los propios clientes**, sobre todo los corporativos:
  algunos prohíben subcontratar el tratamiento de su información o usar herramientas de
  IA sin autorización.
- **Protección de datos personales** (la ley federal aplicable a particulares): cuando los
  documentos contienen datos personales, enviarlos a un proveedor, quizá en el extranjero,
  puede exigir mencionarlo en el aviso de privacidad del despacho y, según el caso,
  obtener consentimiento.
- **Consentimiento informado del cliente.** La práctica prudente es explicar al cliente,
  en la carta de contratación o por escrito, que el despacho usa un asistente de IA
  sobre sus documentos, qué sale y a quién, y obtener su aceptación. Los clientes que no
  acepten simplemente no se activan para la IA.

Texto sugerido (borrador para revisar con asesoría):

> Para analizar los documentos de su asunto con mayor rapidez, el despacho puede usar un
> asistente de inteligencia artificial de un proveedor externo, contratado por el
> despacho bajo condiciones que prohíben usar su información para entrenar modelos.
> Cuando el asistente consulta sus documentos, fragmentos de ellos se transmiten a ese
> proveedor para generar la respuesta. Los documentos se conservan en los servidores del
> despacho. Si usted prefiere que su asunto no se consulte con este asistente, indíquelo
> y no se activará.

## 5. Antes de iniciar el piloto

- [ ] Proveedor y plan de IA elegidos, con contrato que excluye el entrenamiento y
      define la retención.
- [ ] Cuentas de IA del despacho creadas, con verificación en dos pasos.
- [ ] Asesoría confirmó el consentimiento necesario, el aviso de privacidad y las
      cláusulas de clientes.
- [ ] Carta de contratación o aviso a clientes actualizado.
- [ ] Lista de asuntos que **no** se activarán para la IA.
- [ ] Una persona responsable de revisar el registro de actividad y los términos del
      proveedor.
- [ ] Personas usuarias capacitadas con la guía de usuario.
