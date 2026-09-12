# Hallazgos de la API real de genui (verificado contra el código fuente)

Versión instalada: `genui-0.10.3` (paquete auxiliar: `a2ui_core-0.1.1`)

Rutas locales usadas para esta investigación:
- `$HOME/.pub-cache/hosted/pub.dev/genui-0.10.3/lib`
- `$HOME/.pub-cache/hosted/pub.dev/a2ui_core-0.1.1/lib`

## Parseo JSON -> A2uiMessage

`A2uiTransportAdapter.addMessage` (usado para inyectar un mensaje A2UI ya
parseado, en vez de un chunk de texto crudo) tiene esta firma exacta, en
`genui-0.10.3/lib/src/transport/a2ui_transport_adapter.dart` línea 59:

```dart
/// Feeds a raw A2UI message (e.g. from a tool output or separate channel).
void addMessage(core.A2uiMessage message) {
  _messageStream.add(message);
}
```

Donde `core` es el import `import 'package:a2ui_core/a2ui_core.dart' as core;`
(línea 7 del mismo archivo). Es decir: **no** acepta un `Map<String, dynamic>`
directamente — acepta la clase `A2uiMessage` de `a2ui_core`.

Para convertir el `Map<String, dynamic>` crudo (resultado de `jsonDecode` de
un elemento del array `a2ui_messages`) a ese tipo, se usa el factory
constructor real, en `a2ui_core-0.1.1/lib/src/core/messages.dart` línea 23:

```dart
abstract class A2uiMessage {
  final String version;
  A2uiMessage({this.version = 'v0.9'});

  /// Deserializes a JSON envelope into a typed [A2uiMessage].
  factory A2uiMessage.fromJson(Map<String, dynamic> json) {
    ...
  }
}
```

Esta misma factory es la que usa internamente el propio `genui` para parsear
JSON que llega por `addChunk` (texto plano): en
`genui-0.10.3/lib/src/transport/a2ui_parser_transformer.dart` línea 237,
dentro de `_parseMessage`:

```dart
core.A2uiMessage _parseMessage(Map<String, Object?> json) {
  try {
    return core.A2uiMessage.fromJson(json);
  } on core.A2uiValidationError catch (e) { ... }
}
```

**Uso concreto recomendado para Task 6/7:**

```dart
import 'package:a2ui_core/a2ui_core.dart' as core;

final Map<String, dynamic> raw = jsonDecode(elementoDeA2uiMessages);
final core.A2uiMessage message = core.A2uiMessage.fromJson(raw);
adapter.addMessage(message); // adapter es un A2uiTransportAdapter
```

**IMPORTANTE — acción requerida en `pubspec.yaml` para Task 6:**
`a2ui_core` **no** se re-exporta desde `package:genui/genui.dart` (verificado
leyendo el barrel completo, `genui-0.10.3/lib/genui.dart`: exporta
`src/catalog.dart`, `src/development_utilities.dart`, `src/engine.dart`,
`src/facade.dart`, `src/functions.dart`, `src/interfaces.dart`,
`src/model.dart`, `src/primitives.dart`, `src/transport.dart`,
`src/utils.dart`, `src/widgets.dart` — ninguno reexporta tipos de
`a2ui_core`). Hoy `a2ui_core` solo entra como dependencia **transitiva**
(ver `flutter_app/pubspec.lock`: `a2ui_core: dependency: transitive`,
resuelto en `0.1.1`). Si Task 6 escribe
`import 'package:a2ui_core/a2ui_core.dart'`, el linter `flutter_lints`
disparará `depend_on_referenced_packages` porque el paquete no está
declarado directamente en `pubspec.yaml`. **Task 6 debe agregar
explícitamente `a2ui_core: ^0.1.1` a las `dependencies:` de
`pubspec.yaml`** antes de importar ese paquete.

Nota de validación: el `fromJson` exige que `json['version'] == 'v0.9'`
(si no, lanza `A2uiValidationError`), y exige que el mapa tenga **exactamente
una** de las claves `createSurface`, `updateComponents`, `updateDataModel`,
`deleteSurface` (si hay más de una o ninguna, también lanza
`A2uiValidationError`). Ver `a2ui_core-0.1.1/lib/src/core/messages.dart`
líneas 23-52.

## Captura de acciones de botón (confirmar_accion)

**No llega como un evento en `Conversation.events`.** El mecanismo real es:

1. Cuando el usuario interactúa con un widget de un `Surface` (p. ej. tap de
   un botón), el widget catalogado invoca
   `surfaceContext.handleUiEvent(event)` (interfaz `SurfaceContext`, en
   `genui-0.10.3/lib/src/interfaces/surface_context.dart` línea 26):

   ```dart
   abstract interface class SurfaceContext {
     ...
     /// Handles a UI event from this surface.
     void handleUiEvent(UiEvent event);
     ...
   }
   ```

2. La implementación real vive en `SurfaceController`
   (`genui-0.10.3/lib/src/engine/surface_controller.dart` líneas 348-360):

   ```dart
   /// Sends a [UserActionEvent] to [onSubmit] as a [ChatMessage]. No-op for
   /// non-action [UiEvent]s.
   void handleUiEvent(UiEvent event) {
     if (!event.isUserAction) return;
     _onSubmit.add(
       ChatMessage.user(
         '',
         parts: [
           UiInteractionPart.create(
             jsonEncode({'version': 'v0.9', 'action': event.toMap()}),
           ),
         ],
       ),
     );
   }
   ```

   `_onSubmit` es un `StreamController<ChatMessage>.broadcast()` expuesto
   como `Stream<ChatMessage> get onSubmit => _onSubmit.stream;`
   (misma clase, línea 91).

3. `Conversation` se suscribe automáticamente a ese stream en su
   constructor y reenvía cada `ChatMessage` a `sendRequest` — que a su vez
   llama al `onSend` del `A2uiTransportAdapter` (el callback HTTP que ya
   estaba confirmado). Ver `genui-0.10.3/lib/src/facade/conversation.dart`
   línea 156:

   ```dart
   // Listen for controller submissions (e.g. errors or user actions) and
   // forward them.
   _engineSubmitSubscription = controller.onSubmit.listen(sendRequest);
   ```

   Es decir: la acción del botón viaja automáticamente de vuelta al backend
   sin que la app tenga que escuchar `Conversation.events` ni ningún
   callback separado — basta con haber construido el `Conversation` con el
   `controller` y el `transport` correctos, y basta con que el `onSend` del
   `A2uiTransportAdapter` esté implementado (ya confirmado en el README).
   `Conversation.events` sí emite eventos (`ConversationSurfaceAdded`,
   `ConversationComponentsUpdated`, `ConversationSurfaceRemoved`,
   `ConversationContentReceived`, `ConversationWaiting`,
   `ConversationError` — ver `conversation.dart` líneas 16-74), pero
   **ninguno de esos tipos representa la acción de botón en sí**; esa
   acción solo es observable indirectamente si se envuelve/interpone el
   `onSend` del transport adapter (que sí recibe el `ChatMessage`
   resultante) o si se escucha `SurfaceController.onSubmit` directamente.

**Forma exacta de los datos de la acción** — clase `UserActionEvent`
(extension type sobre `UiEvent`), en
`genui-0.10.3/lib/src/model/ui_models.dart` líneas 54-78:

```dart
extension type UserActionEvent.fromMap(JsonMap _json) implements UiEvent {
  UserActionEvent({
    String? surfaceId,
    required String name,
    required String sourceComponentId,
    DateTime? timestamp,
    JsonMap? context,
  }) : _json = {
         surfaceIdKey: ?surfaceId,
         'name': name,
         'sourceComponentId': sourceComponentId,
         'timestamp': (timestamp ?? DateTime.now()).toIso8601String(),
         'context': context ?? {},
       };

  String get name => _json['name'] as String;
  String get sourceComponentId => _json['sourceComponentId'] as String;
  JsonMap get context => _json['context'] as JsonMap;
}
```

`UiEvent.isUserAction` se determina por `_json.containsKey('name')`
(`ui_models.dart` línea 47).

Lo que finalmente sale por el `onSend` del `A2uiTransportAdapter` (dentro
del `ChatMessage.user(...)`, como `UiInteractionPart`) es un JSON con esta
forma (reconstruido de `surface_controller.dart` línea 357):

```json
{
  "version": "v0.9",
  "action": {
    "surfaceId": "...",
    "name": "confirmar_accion",
    "sourceComponentId": "boton_confirmar",
    "timestamp": "2026-09-12T...",
    "context": { "proposalId": "..." }
  }
}
```

El campo `name` es el nombre de la acción (ej. `confirmar_accion`) y
`context` es un mapa libre. **Verificado que sí se puebla realmente** (no es
solo un default `{}` del constructor): el único llamador real de
`UserActionEvent(...)` con `context:` no vacío está en
`genui-0.10.3/lib/src/catalog/basic_catalog_widgets/button.dart`
líneas 201-219 (el catálogo básico del botón, `Button`/`ButtonGroup`):

```dart
Future<void> _handlePress(
  CatalogItemContext itemContext,
  _ButtonData buttonData,
) async {
  final JsonMap actionData = buttonData.action;
  if (actionData.containsKey('event')) {
    final eventMap = actionData['event'] as JsonMap;
    final actionName = eventMap['name'] as String;
    final contextDefinition = eventMap['context'] as JsonMap?;

    final JsonMap resolvedContext = await resolveContext(
      itemContext.dataContext,
      contextDefinition,
    );
    itemContext.dispatchEvent(
      UserActionEvent(
        name: actionName,
        sourceComponentId: itemContext.id,
        context: resolvedContext,
        ...
```

Es decir: `context` se llena a partir de la propiedad `action.event.context`
que trae la **definición JSON del botón** en el A2UI que manda el servidor
(el catálogo básico define ese esquema —ver `A2uiSchemas.action()` usado en
`button.dart`/`text_field.dart`—, y `resolveContext` resuelve bindings del
`dataContext` de la surface contra ese `contextDefinition`). Por lo tanto,
**si el servidor incluye `proposalId` dentro de `action.event.context` en el
JSON del botón, ese valor sí llega íntegro hasta `UserActionEvent.context`
y de ahí hasta el JSON final que recibe `onSend`** (confirmado, no
hipótesis). Si el servidor NO pone `proposalId` ahí, no aparecerá — el
mecanismo de transporte es correcto y probado en código real, pero el
contenido de `context` depende enteramente del payload A2UI que genere el
backend, y eso está fuera del alcance de esta tarea (que solo verifica
`genui`).

## Widget Surface — parámetros exactos del constructor

Firma real, copiada de `genui-0.10.3/lib/src/widgets/surface.dart`
líneas 24-44:

```dart
class Surface extends StatefulWidget {
  /// Creates a [Surface].
  const Surface({
    super.key,
    required this.surfaceContext,
    this.defaultBuilder,
    this.actionDelegate = const DefaultActionDelegate(),
  });

  /// The context that holds the state of this surface.
  final SurfaceContext surfaceContext;

  /// A builder for the widget to display when the surface has no definition.
  final WidgetBuilder? defaultBuilder;

  /// The delegate that handles UI actions.
  final ActionDelegate actionDelegate;

  @override
  State<Surface> createState() => _SurfaceState();
}
```

**Esto contradice el borrador del plan.** `Surface` NO recibe `host:` ni
`surfaceId:` como parámetros directos. El único parámetro requerido es
`surfaceContext` (tipo `SurfaceContext`, definido en
`genui-0.10.3/lib/src/interfaces/surface_context.dart`). Los parámetros
opcionales son `defaultBuilder` (widget a mostrar mientras no hay
definición) y `actionDelegate` (por defecto `DefaultActionDelegate()`).

Para obtener el `SurfaceContext` correcto a partir del `surfaceId` (el que
llega en `ConversationSurfaceAdded.surfaceId`), se usa
`SurfaceController.contextFor`, en
`genui-0.10.3/lib/src/engine/surface_controller.dart` líneas 101-104:

```dart
@override
SurfaceContext contextFor(String surfaceId) {
  return _ControllerContext(this, surfaceId);
}
```

Uso concreto:

```dart
Surface(surfaceContext: surfaceController.contextFor(surfaceId))
```

**Sí existe un hook para interceptar acciones localmente antes de que se
reenvíen al backend: `actionDelegate`.** Leído completo
`genui-0.10.3/lib/src/widgets/surface.dart` líneas 145-207. El flujo real es:

```dart
void _dispatchEvent(UiEvent event) {
  if (widget.actionDelegate.handleEvent(
    context,
    event,
    widget.surfaceContext,
    _buildWidget,
  )) {
    return; // el delegate ya manejó el evento; no se reenvía al backend
  }

  final Map<String, Object?> eventMap = {
    ...event.toMap(),
    surfaceIdKey: widget.surfaceContext.surfaceId,
  };
  final UiEvent newEvent = event.isUserAction
      ? UserActionEvent.fromMap(eventMap)
      : UiEvent.fromMap(eventMap);
  widget.surfaceContext.handleUiEvent(newEvent);
}

abstract interface class ActionDelegate {
  /// Returns `true` if the event was handled, `false` otherwise.
  bool handleEvent(
    BuildContext context,
    UiEvent event,
    SurfaceContext genUiContext,
    Widget Function(SurfaceDefinition, Catalog, String, DataContext)
    buildWidget,
  );
}

class DefaultActionDelegate implements ActionDelegate {
  const DefaultActionDelegate();

  @override
  bool handleEvent(...) => false; // no maneja nada; siempre reenvía
}
```

Es decir: todo tap de un widget del catálogo pasa primero por
`Surface.actionDelegate.handleEvent(...)`. Si ese método devuelve `true`
(evento manejado localmente), el evento **no** llega a
`surfaceContext.handleUiEvent` y por lo tanto **no** se reenvía al backend.
El `DefaultActionDelegate` (usado si no se pasa `actionDelegate` al
constructor) siempre devuelve `false`, así que por defecto toda acción de
usuario se reenvía automáticamente al backend como se describe arriba. Si
Task 6/7 necesita, por ejemplo, mostrar un diálogo de confirmación local
antes de reenviar `confirmar_accion`, el punto de extensión correcto es
implementar un `ActionDelegate` propio y pasarlo como
`Surface(surfaceContext: ..., actionDelegate: MiActionDelegate())` — no hay
que tocar `SurfaceController` ni `Conversation` para eso.
