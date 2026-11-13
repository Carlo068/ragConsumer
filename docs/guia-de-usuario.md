# Guía de usuario

Para abogadas y abogados del despacho. No necesita conocimientos técnicos.

## Qué hace este sistema

Usted guarda los documentos de cada **asunto** en un lugar privado del despacho.
Después conecta su **asistente de IA** (Claude, ChatGPT u otro) y le pide que busque
en esos documentos: «¿en qué archivo está la cláusula de rescisión?», «resume lo que
dicen mis documentos sobre el pago de la renta».

- Cada asunto está separado de los demás. Solo ve los asuntos a los que lo agregaron.
- Su asistente de IA solo puede buscar en los asuntos que **usted** active, y solo
  mientras usted siga teniendo acceso a ellos.
- Todo queda registrado: quién entró, quién subió o eliminó un archivo y cada búsqueda
  que hizo un asistente de IA.

## 1. Entrar por primera vez

1. El administrador del despacho le envía un **enlace de invitación** por correo. Sirve
   **una sola vez** y vence a las **72 horas**. Si ya no funciona, pídale otro.
2. Abra el enlace, elija una contraseña de **al menos 12 caracteres** y repítala. Una
   frase larga que usted recuerde es mejor que una palabra con números.
3. Ya puede iniciar sesión con su correo y su contraseña. La sesión se cierra sola
   después de 12 horas; solo vuelva a iniciarla.

Para salir use **Cerrar sesión**, sobre todo en una computadora compartida.

## 2. Sus asuntos

Al entrar verá la lista de **Asuntos**. Para crear uno, pulse **Nuevo**, escriba el
nombre y pulse **Crear**. Quien lo crea queda como **Responsable**.

En cada asunto hay tres funciones:

| Función | Qué puede hacer |
|---|---|
| **Lector** | Buscar y ver los archivos |
| **Editor** | Además, agregar y quitar archivos |
| **Responsable** | Además, administrar el asunto y a sus integrantes |

## 3. Subir archivos y carpetas

Abra el asunto. Si es Editor o Responsable verá un recuadro para subir:

- **Arrastre** archivos, una **carpeta** completa o un archivo **.zip** al recuadro, o
  use **Elegir archivos** o **Elegir carpeta**.
- Se aceptan **PDF, Word (.docx y .doc), correos (.eml y .msg) y archivos de texto**.
  Cada archivo tiene un tamaño máximo, que el recuadro le indica.
- Antes de subir, el sistema le muestra una **revisión**: cuántos archivos se subirán y
  cuáles se omitirán y por qué (archivos de sistema, tipos que no se pueden leer,
  vacíos, demasiado grandes o repetidos). Revise y pulse **Subir**.
- Las carpetas conservan su estructura: verá, por ejemplo,
  «contratos/2024/arrendamiento.pdf».

### Qué pasa después de subir

Cada archivo pasa por estos estados:

| Lo que ve | Qué significa |
|---|---|
| **En espera** | Subió bien y espera su turno |
| **Leyendo…** | El sistema está leyendo el texto. Los archivos grandes o los escaneos tardan más |
| **Listo para buscar** | Ya puede encontrarlo su asistente de IA |
| **No se pudo leer** | Debajo del archivo aparece la razón y qué hacer |

Su asistente de IA **solo encuentra lo que está «Listo para buscar»**. Después de
subir muchos archivos, espere a que terminen antes de preguntar.

**Escaneos y fotografías de documentos:** el sistema los lee con reconocimiento de
texto. Funciona bien con escaneos claros y derechos; con páginas tenues, borrosas o
chuecas puede fallar. En ese caso la razón dirá que no se encontró texto: vuelva a
escanear con más calidad.

Para quitar un archivo, use el botón de eliminar junto a él. **Eliminar es
permanente** y no se puede deshacer. Lo mismo para un asunto completo (solo un
Responsable puede eliminarlo o cambiarle el nombre).

## 4. Compartir un asunto con un colega

1. Abra el asunto y busque **Personas con acceso**.
2. En **Agregar a alguien que ya tiene cuenta** escriba su correo, elija su función y
   agréguelo. (Solo los Responsables pueden hacerlo.)
3. Si la persona **todavía no tiene cuenta**, el administrador debe invitarla primero en
   **Usuarios e invitaciones**. **Invitar no da acceso a ningún asunto**: después hay que
   agregarla a cada asunto, uno por uno.

Para quitar a alguien, o cambiar su función, use los controles junto a su nombre. Pierde
el acceso de inmediato, y su asistente de IA también. Cualquier persona puede
**Salir** de un asunto; un asunto siempre debe conservar al menos un Responsable.

## 5. Conectar su asistente de IA

Se hace **una sola vez**. Abra **Conectar IA**, que lo guía en cuatro pasos:

1. **Elija qué asuntos puede ver su IA.** Active el interruptor «Permitir que mi IA
   busque en…» de cada asunto que quiera. Lo que usted active es **solo para usted**:
   no cambia lo que ve la IA de un colega. También lo puede hacer desde la lista de
   asuntos.
2. **Cree su llave de acceso personal.** Escriba un nombre (por ejemplo, «Claude en mi
   laptop») y pulse **Crear llave de acceso**. La llave se muestra **una sola vez**:
   cópiela en ese momento.
3. **Péguela en su asistente de IA.** Agregue una conexión nueva (puede llamarse
   «servidor MCP» o «conector») y escriba los dos datos que le muestra la pantalla: la
   **dirección del servidor** y la **llave**.
4. **Pruebe con una pregunta**, por ejemplo: «¿Qué archivos tengo en mis asuntos?»

Sobre la llave:

- **Trátela como una contraseña.** Quien la tenga puede buscar en sus asuntos.
- Cree **una por dispositivo o aplicación**. Puede tener hasta 10 y cada una vence a los
  90 días.
- Si la pierde, o cree que alguien la vio, pulse **Revocar** en esa misma pantalla:
  deja de funcionar de inmediato. Después cree otra.

## 6. Cómo hacer buenas preguntas

El asistente busca en sus documentos y le responde con lo que encuentra. Obtendrá mejores
respuestas si:

- **Es concreto.** «¿Qué dice el convenio de terminación sobre el finiquito?» funciona
  mejor que «¿qué hay sobre el cliente?».
- **Pide la fuente.** Añada: «indícame en qué archivo y en qué pasaje lo encontraste».
  Así puede abrir el documento y comprobarlo.
- **Hace una pregunta a la vez**, y luego sigue conversando: «ahora compáralo con el
  contrato de 2023».
- **Menciona el asunto o el documento** cuando lo sepa: «en el asunto de la
  arrendadora, busca…».
- **Prueba otras palabras si no encuentra nada.** La búsqueda entiende el sentido, pero
  también las palabras exactas: si el contrato dice «rescisión», pruebe esa palabra
  además de «terminar anticipadamente».
- **Pide que diga cuándo no encuentra.** «Si no aparece en los documentos, dímelo; no
  lo supongas.»

Ejemplos:

> Busca en mis documentos las cláusulas de rescisión y dime en qué archivo están.
>
> Resume lo que dicen mis documentos sobre el pago de la renta e indica los archivos.
>
> ¿Qué fechas límite aparecen en los documentos del asunto? Haz una lista con el archivo
> de cada una.

**Siempre compruebe lo importante en el documento original** (montos, fechas, nombres,
citas). Un asistente de IA puede equivocarse o resumir mal. Es una ayuda para encontrar y
leer más rápido; no sustituye su criterio ni su revisión.

## 7. Confidencialidad: qué sale del servidor

Sus documentos se guardan en el servidor del despacho. Pero cuando su asistente de IA
hace una búsqueda, **los pasajes que encuentra se envían a la empresa que ofrece ese
asistente** (Anthropic, OpenAI u otra) para que pueda responderle. El sistema no puede
impedirlo. Por eso:

- Use solo la cuenta y el plan de IA que el despacho haya autorizado.
- Active la IA **solo en los asuntos** donde corresponda.
- Antes de usarla con información de un cliente, confirme con el despacho si necesita su
  consentimiento. Lea el **aviso de confidencialidad** del despacho
  (`docs/aviso-de-confidencialidad.md`).

## 8. Si algo no funciona

| Qué ve | Qué hacer |
|---|---|
| «Su sesión terminó» | Inicie sesión de nuevo |
| El enlace de invitación «no es válido o ya venció» | Pida otro al administrador |
| «Ese asunto no existe o usted no tiene acceso a él» | Pida a un Responsable del asunto que lo agregue |
| «Su función en este asunto no permite hacer eso» | Pida a un Responsable que le cambie la función |
| Un archivo dice **No se pudo leer** | Lea la razón que aparece debajo del archivo: dice si es un escaneo poco claro, un archivo dañado o con contraseña, o un problema temporal que se resuelve intentando de nuevo |
| «El índice de búsqueda de este asunto… hay que reconstruirlo» | Avise al administrador |
| La IA no encuentra algo que usted sabe que está | Revise que el archivo diga **Listo para buscar**, que el interruptor del asunto esté activo, y pruebe otras palabras |
| Perdió su llave de acceso | Revóquela en **Conectar IA** y cree otra |

El administrador del despacho puede consultar el **Registro de actividad** (quién hizo
qué y cuándo, incluidas las búsquedas de la IA). Los registros no se pueden modificar ni
eliminar.
