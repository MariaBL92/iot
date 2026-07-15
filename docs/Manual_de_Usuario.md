Manual de Usuario
Sistema de verificación de integridad
de datos IoT con IOTA
Guía paso a paso para usuarios sin conocimientos avanzados de programación

Mayo de 2026
 1. ¿Qué es este sistema?
Este sistema permite comprobar si unos datos recogidos por sensores —por ejemplo, lecturas de temperatura o humedad— han sido modificados después de ser registrados. Es una herramienta de detección de manipulaciones: no impide que alguien altere los datos, pero garantiza que cualquier alteración, por pequeña que sea, será detectada.
Analogía:  Imagine que escribe un texto en un sobre, lo lacra con un sello único, y lo deposita en una caja fuerte transparente que cualquiera puede ver pero nadie puede abrir. Más adelante, si alguien pretende que ese texto era distinto, basta con comparar el sello: si coincide, el texto es el original; si no coincide, alguien lo alteró. Este sistema hace exactamente eso, pero con datos digitales en lugar de papel.
El sistema es un prototipo experimental desarrollado como Trabajo Fin de Máster. No utiliza sensores físicos: los simula por software. Esto permite demostrar la viabilidad de la propuesta tecnológica sin coste de hardware y de forma reproducible.
2. ¿Qué problema resuelve?
Cada vez más decisiones importantes se toman basándose en datos generados por dispositivos conectados (sensores ambientales, equipos médicos, cadena de frío de alimentos y medicamentos, monitores agrícolas o industriales). Estos datos viajan por redes y se guardan en bases de datos antes de llegar a quien los analiza. En todo ese camino pueden ocurrir tres cosas problemáticas:
•	Manipulación intencionada. Alguien con acceso al sistema puede modificarlos intencionadamente.
•	Alteración accidental. Un error técnico o una corrupción de datos puede alterarlos sin querer.
•	Repudio. Alguien puede negar que un dato concreto fuera el que en su momento se registró.
Los métodos tradicionales para resolver este problema dependen de una autoridad central de confianza: un servidor protegido, una base de datos con permisos, una auditoría. Pero todos esos sistemas tienen un punto débil: si alguien con acceso privilegiado al servidor decide manipular los datos, puede hacerlo sin dejar rastro.
Este sistema propone una alternativa: en lugar de confiar en una sola autoridad, se utiliza una red distribuida y pública —el Tangle de IOTA— donde los registros no pueden modificarse una vez escritos, ni siquiera por la persona que los creó.
3. ¿Cómo funciona? (visión sin tecnicismos)
El funcionamiento descansa en dos conceptos sencillos: la huella digital y el registro inmutable. Si entiende estos dos, ha entendido el sistema.
3.1 La huella digital (hash)
Una huella digital, en este contexto, es un código corto que se calcula a partir del contenido de un dato. Tiene tres propiedades cruciales:
•	Determinismo. Si dos datos son idénticos, su huella es idéntica.
•	Sensibilidad. Si dos datos difieren en lo más mínimo —un solo dígito, una coma— las huellas son completamente diferentes.
•	Privacidad. A partir de la huella es prácticamente imposible reconstruir el dato original. La huella revela que existió un dato, pero no lo expone.
Técnicamente, este sistema utiliza una función llamada SHA-256, que produce huellas de 64 caracteres. Por ejemplo, una lectura de un sensor puede tener esta huella:
b3a81c9771832c3088deb2cba56e1f8c97a5d3f1abc7e8b9a02f4c5d6e7a8b9c

Si el sensor lee 23.5 °C, la huella es una. Si por alguna razón ese dato se modifica a 23.6 °C, la huella ya no será la misma. Eso es lo que permite detectar alteraciones.
3.2 El registro inmutable (Tangle de IOTA)
Una vez calculada la huella digital del dato, hay que guardarla en algún sitio donde no pueda ser alterada. Si la guardáramos en una base de datos normal, alguien con acceso podría modificar el dato Y la huella, y nadie se enteraría.
En el caso de este prototipo, se utiliza un nodo IOTA privado que corre localmente mediante Docker. El Tangle de IOTA es una red distribuida y pública mantenida por miles de nodos en todo el mundo, donde una vez escrita una entrada queda visible para todos y no puede ser modificada ni borrada. Es parecida a las cadenas de bloques (blockchains), pero con tres ventajas para este caso:
•	Sin costes. Es gratuita, no cobra comisiones por escribir.
•	Orientada a IoT. Está diseñada específicamente para almacenar gran cantidad de pequeños registros, como los que genera el Internet de las Cosas.
•	Auditable. Es pública: cualquiera puede consultar lo registrado y verificarlo de forma independiente.
Importante:  En el Tangle solo se guarda la huella digital, nunca el dato original. Los valores del sensor (temperatura, humedad) permanecen únicamente en el ordenador local. Esto protege la privacidad de la información sin renunciar a la auditabilidad.
3.3 La verificación
Cuando alguien quiere comprobar si un dato es el original, el sistema realiza dos pasos: (1) recupera la huella original desde el Tangle —que es inviolable—, y (2) calcula la huella del dato que tiene delante. Si las dos huellas coinciden, el dato es íntegro. Si no coinciden, el dato ha sido alterado en algún momento desde que se registró. La siguiente figura ilustra este proceso:
 
Figura 1. Proceso de verificación de integridad.
4. Las cuatro partes del sistema
Para que todo lo anterior funcione, el sistema se organiza en cuatro partes que trabajan en secuencia. Cada parte tiene una responsabilidad bien definida:
•	Capa 1 — Simulación de sensores: genera datos artificiales que imitan lo que produciría un sensor real (temperatura y humedad cada pocos segundos). Se usa simulación porque el objetivo del trabajo es demostrar la propuesta, no probar el hardware.
•	Capa 2 — Procesamiento: recibe esos datos, calcula su huella digital y los guarda en un registro local. Es como un escribano que toma nota y prepara cada documento antes de archivarlo.
•	Capa 3 — Registro en el Tangle: envía la huella digital al Tangle de IOTA, donde queda registrada de forma inmutable. A partir de ese momento, ese registro vive en la red distribuida y puede ser consultado por cualquiera.
•	Capa 4 — Verificación: dado un identificador de un registro en el Tangle, recupera la huella, la compara con la huella recalculada del dato actual, y emite un veredicto: íntegro o alterado.
 
Figura 2. Arquitectura del sistema y flujo de datos entre capas.
5. Glosario de términos
A lo largo del manual aparecen algunos términos técnicos que conviene tener a mano. Aquí se explican en lenguaje sencillo:
Término	Significado en este sistema
IoT (Internet of Things)	Conjunto de dispositivos conectados que recogen datos del entorno (sensores).
Hash / Huella digital	Código corto y único que representa un dato. Si el dato cambia, el código cambia.
SHA-256	El algoritmo concreto que se usa para calcular las huellas. Estándar reconocido.
Tangle	Red distribuida pública (similar a una blockchain) donde se registran las huellas.
IOTA	Organización y tecnología que desarrolla y mantiene el Tangle.
Testnet	Red de pruebas del Tangle: gratuita, sin valor real, pensada para experimentar.
MQTT	Protocolo de mensajería ligero que utilizan los sensores IoT para enviar datos.
Mosquitto	Programa que actúa como intermediario de mensajes MQTT en el ordenador local.
Block / Bloque	Una entrada concreta en el Tangle. Tiene un identificador único (block_id).
JSON	Formato de texto estructurado, fácil de leer, usado para intercambiar datos.
Terminal / Consola	Ventana donde se escriben órdenes al ordenador con texto, sin ratón.
Python	Lenguaje de programación en el que está escrito el sistema.
Registro local	Archivo en el ordenador que guarda los datos originales y su huella.
Veredicto	Resultado de la verificación: ÍNTEGRO (sin alterar) o ALTERADO (manipulado).

 6. Antes de empezar: requisitos
Para ejecutar el sistema necesita instalar tres programas en su ordenador. Los tres son gratuitos y de uso libre. Para cada uno se explica para qué sirve y dónde descargarlo. No se preocupe si los nombres le resultan desconocidos: el manual le guía paso a paso.
6.1 Python (versión 3.11 o superior)
Es el lenguaje en el que está escrito el sistema. Para ejecutar los programas, su ordenador necesita tener Python instalado. Compruebe si ya lo tiene escribiendo en una terminal:
python3 --version

Si aparece un número como 3.11 o superior, ya está listo. Si no, descárguelo desde python.org y siga las instrucciones del instalador. En Linux y macOS suele venir preinstalado; en Windows hay que descargarlo manualmente.
6.2 Rust (compilador del componente IOTA)
El componente que conecta con el Tangle de IOTA está escrito en parte en otro lenguaje llamado Rust. No tiene que aprenderlo: solo necesita tenerlo instalado para que la instalación del sistema funcione. Visite rust-lang.org/tools/install y siga las instrucciones de instalación de rustup, que es el instalador oficial.
Consejo:  Si está en Windows, considere usar WSL2 (Windows Subsystem for Linux). Le evitará varios problemas comunes al compilar Rust y otros componentes del sistema.
6.3 Mosquitto (broker MQTT)
Es el intermediario que reparte los mensajes que envían los sensores simulados a los componentes que los procesan. Instalación según el sistema operativo:
# En macOS (con Homebrew):
brew install mosquitto

# En Ubuntu/Debian:
sudo apt install mosquitto mosquitto-clients

# En Fedora:
sudo dnf install mosquitto mosquitto-clients

6.4 Docker y Docker Compose
El nodo IOTA local se levanta con Docker. Necesita tener Docker Desktop (macOS/Windows) o Docker Engine + Docker Compose (Linux) instalados. Descárguelos desde docker.com. No necesita cuenta ni suscripción de pago: la versión gratuita es suficiente. Una conexión a internet sólo es necesaria la primera vez para descargar las imágenes Docker; después, el sistema funciona completamente sin red.
7. Instalación paso a paso
Una vez que tiene los requisitos del apartado anterior, siga estos cuatro pasos. Todos los comandos se escriben en una terminal.
Paso 1 — Obtener el código del sistema
El código del sistema vive en un repositorio Git. Clónelo y entre en la carpeta:
git clone <dirección-del-repositorio>
cd iot
Si la persona responsable del proyecto le entregó el código como un archivo ZIP, descomprímalo y abra una terminal en la carpeta resultante.
Paso 2 — Crear un entorno aislado de Python
Un "entorno virtual" es como una carpeta aislada donde se instalan los componentes del sistema sin afectar al resto del ordenador. Esto evita conflictos con otros programas que también usen Python.
python3 -m venv venv
source venv/bin/activate     # en Windows: venv\Scripts\activate

Después de ejecutar la segunda línea, debería ver que su terminal muestra el prefijo (venv) al principio de cada línea. Eso indica que está dentro del entorno aislado.
Paso 3 — Instalar las dependencias
El sistema utiliza varios componentes auxiliares (librerías). Para instalarlos todos de una vez:
pip install -r requirements.txt

Este paso puede tardar varios minutos la primera vez, sobre todo por la compilación del componente IOTA (que es la parte donde interviene Rust). Si todo va bien, al final del proceso no debería aparecer ningún error.
Paso 4 — Crear el archivo de configuración
El sistema lee algunos parámetros (dirección del broker, dirección del nodo IOTA, ruta del registro local) de un archivo llamado .env. Cree el suyo a partir de la plantilla incluida:
cp .env.example .env

Los valores por defecto ya están configurados para el nodo IOTA local (IOTA_NODE_URL= http://localhost:14265/api/core/v2/info). Solo necesita modificar otros valores si su entorno es especial (por ejemplo, si Mosquitto corre en otro ordenador o en otro puerto).
Paso 5 — Levantar el Private Tangle (nodo IOTA local)
Dado que los testnets públicos de IOTA Stardust están fuera de servicio desde mayo de 2025, el sistema utiliza un nodo IOTA privado que corre en su propio ordenador mediante Docker. Solo necesita hacer este paso una vez: después, los contenedores quedan guardados y se pueden volver a levantar con un solo comando.
Si es la primera vez, clone el repositorio de Hornet y ejecute el bootstrap:
git clone https://github.com/iotaledger/hornet.git cd hornet/private_tangle ./bootstrap.sh
A continuación, levante los contenedores (2 nodos + coordinador):
./run.sh 4
El proceso tarda entre 10 y 15 minutos en estar completamente operativo. Para comprobar que está funcionando, abra su navegador y vaya a http://localhost:8011 (usuario: admin, contraseña: admin). El indicador verde en el panel confirma que el coordinador está emitiendo milestones y el nodo está listo.
Nota para macOS:  Si el contenedor inx-coordinator se cae durante el arranque, reinícielo manualmente: 'docker compose start inx-coordinator'. Suele ocurrir solo en el primer arranque.
En las sesiones siguientes (sin necesidad de repetir bootstrap ni run.sh), solo ejecute:
cd hornet/private_tangle 
docker compose --profile "4-nodes" start
Durante el desarrollo experimental, se evidenció que un apagado abrupto del equipo —sin detener previamente los contenedores de forma ordenada— puede provocar la corrupción de la base de datos local del nodo Hornet, manifestándose como un fallo de tipo panic en el componente tangle al intentar reiniciar el servicio (código de salida 2), o como una finalización forzosa de los contenedores (código de salida 137). Ante este escenario, el propio repositorio provee un script de limpieza (cleanup.sh), el cual permite eliminar los contenedores y datos afectados, posibilitando reiniciar la red desde cero mediante una nueva ejecución de bootstrap.sh seguida de run.sh. Como medida preventiva, se estableció como buena práctica detener los contenedores de forma explícita mediante 
docker compose --profile "4-nodes" stop
antes de apagar el equipo, evitando así la necesidad de reiniciar la red en sesiones futuras.
8. Cómo usar el sistema
El sistema se ejecuta en cuatro terminales paralelas. Suena a más de lo que es: cada terminal lanza un componente del sistema y deja que corra en segundo plano mientras usted observa lo que sucede. Si su sistema lo permite, abra cuatro pestañas de terminal.
Recordatorio:  En cada terminal donde vaya a ejecutar comandos del sistema, debe estar dentro de la carpeta del proyecto y haber activado el entorno virtual con "source venv/bin/activate" (o "venv\Scripts\activate" en Windows). Si no ve el prefijo (venv) en la línea de comandos, repita esa orden.
Terminal 1 — Arrancar el broker MQTT
Inicia el servicio que distribuye los mensajes entre componentes:
mosquitto -v

El parámetro -v hace que muestre en pantalla todo lo que ocurre, lo que ayuda a ver que efectivamente está funcionando. Deje esta terminal abierta.
Terminal 2 — Iniciar el simulador de sensores
Genera lecturas artificiales y las publica cada dos segundos:
make simulate

Verá aparecer mensajes como este, uno cada dos segundos:
Published: {"sensor_id": "sensor_01", "timestamp": "2026-05-12T14:35:22Z", "temperature": 24.7, "humidity": 58.3}

Terminal 3 — Iniciar el procesador y registrador
Esta es la parte central: recibe cada mensaje, calcula su huella, lo guarda localmente, y lo registra en el Tangle de IOTA:
make subscribe

Verá aparecer mensajes como este:
Connected and subscribed to iot/sensors
Registered in Tangle: sensor=sensor_01 hash=b3a81c977... block_id=0x1234abc...

Cada vez que aparece un "Registered in Tangle", una huella ha quedado anclada permanentemente en la red IOTA. Anote algún block_id; lo va a necesitar para verificar después.
Terminal 4 — Observar el registro local
El sistema mantiene en un archivo local todos los datos originales junto con sus huellas y sus identificadores en el Tangle. Para verlo crecer en tiempo real:
tail -f data/local_registry.json

Cada entrada tiene esta forma:
{
  "block_id":  "0x1234abc...",
  "hash":      "b3a81c977...",
  "timestamp": "2026-05-12T14:35:22Z",
  "raw_data": {
    "sensor_id":   "sensor_01",
    "timestamp":   "2026-05-12T14:35:22Z",
    "temperature": 24.7,
    "humidity":    58.3
  },
  "status": "registered"
}

El campo "status" puede valer registered (todo correcto), pending (calculado pero aún no enviado al Tangle) o failed (no se pudo registrar tras varios reintentos).
9. Verificar la integridad de un registro
Esta es la funcionalidad principal del sistema. Una vez que tiene un registro anotado en el Tangle, puede comprobar en cualquier momento si los datos asociados siguen siendo los originales.
9.1 Verificación normal (debería dar ÍNTEGRO)
Tome un block_id que apareció en su Terminal 3 y ejecútelo en una terminal:
make verify BLOCK_ID=0x1234abc...

La respuesta esperada es:
================================================================
  VERDICTO: INTEGRO
================================================================
  block_id:  0x1234abc...
  sensor_id: sensor_01
  timestamp: 2026-05-12T14:35:22Z
  stored:    b3a81c977...
  computed:  b3a81c977...
  match:     True
================================================================

El sistema ha recuperado la huella original del Tangle, ha recalculado la huella del dato actual, y ha comprobado que coinciden. Resultado: ÍNTEGRO.
9.2 Verificación tras alterar los datos (debería dar ALTERADO)
Para demostrar que el sistema detecta cambios, simulemos una manipulación. Edite el archivo data/local_registry.json con un editor de texto, encuentre la entrada correspondiente al block_id que está verificando, y cambie un valor numérico. Por ejemplo, cambie temperatura 24.7 por 24.8. Guarde el archivo y vuelva a verificar:
make verify BLOCK_ID=0x1234abc...

Esta vez la respuesta será:
================================================================
  VERDICTO: ALTERADO
================================================================
  stored:   b3a81c977...     ← lo que está en el Tangle
  computed: a92fc101e...     ← lo que da el dato modificado
  match:    False
================================================================

Al ser la huella distinta, el sistema concluye que los datos han cambiado desde que se registraron originalmente. El Tangle no puede modificarse, así que la huella ahí guardada es de fiar; la diferencia revela la manipulación local.
Reflexión:  Esto demuestra el valor del sistema: aunque alguien tenga acceso completo al ordenador local y modifique los datos, NO puede modificar la huella en el Tangle. La verificación siempre delatará la manipulación.
10. Pruebas de validación del sistema
Para demostrar que el sistema funciona correctamente y para obtener datos cuantitativos sobre su rendimiento, el proyecto incluye un conjunto de pruebas automatizadas.
10.1 Pruebas de detección (escenarios E1-E6)
El sistema se somete a seis escenarios distintos: uno con datos íntegros (debe decir ÍNTEGRO) y cinco con datos alterados de distintas maneras (debe decir ALTERADO). Para ejecutarlas:
make bench-scenarios

El resultado se guarda en docs/results/scenarios.csv. Cada fila indica si el veredicto del sistema coincidió con el esperado. La tasa de detección, en condiciones normales, debe ser del 100 %.
10.2 Pruebas de tiempo (latencia)
Estas pruebas miden cuánto tarda el sistema en registrar una huella en el Tangle ("T_reg") y cuánto tarda en verificar una posteriormente ("T_ver"). Se ejecutan cien veces y se calcula la media, la mediana y otros estadísticos:
make bench-latency

El resultado se guarda en cd. La duración total de la prueba depende de la velocidad de la red IOTA Testnet: suele estar entre cinco y veinte minutos.
10.3 Análisis y generación de gráficas
Una vez ejecutadas las dos pruebas anteriores, se generan un resumen estadístico y dos figuras (histograma y diagrama de cajas):
make bench-analyze

Las salidas se guardan en:
•	docs/results/summary.txt: resumen legible con todas las métricas calculadas.
•	docs/results/figures/latency_histogram.png: distribución de las latencias de registro y verificación.
•	docs/results/figures/latency_boxplot.png: comparación visual de ambas distribuciones.
11. Si algo no funciona (FAQ)
Esta sección recoge los problemas más habituales y sus soluciones. Si ninguna le ayuda, contacte con la persona responsable del proyecto.
"command not found: mosquitto"
Mosquitto no está instalado o no está en el PATH del sistema. Reinstálelo siguiendo el paso 6.3, y verifique que escribiendo "mosquitto -h" en la terminal aparece su pantalla de ayuda.
"Failed to install iota-sdk"
Probablemente Rust no esté instalado o no esté actualizado. Vuelva al paso 6.2, y compruebe con "rustc --version" que muestra una versión reciente. Si el problema persiste, asegúrese de tener un compilador de C++ instalado (Xcode Command Line Tools en macOS, build-essential en Ubuntu).
Mensaje "Tangle registration failed"
El nodo IOTA local no respondió. Lo más habitual es que los contenedores Docker del private tangle no estén corriendo o que el coordinador se haya caído durante el arranque. Compruebe el estado con 'docker compose ps' dentro de la carpeta hornet/private_tangle: todos los servicios deberían aparecer como 'Up'. Si el contenedor 'inx-coordinator' aparece como 'Exit', reinícielo con 'docker compose start inx-coordinator' y espere uno o dos minutos a que el nodo vuelva a emitir milestones. El sistema reintenta automáticamente hasta tres veces.
La verificación da NO_ENCONTRADO en lugar de ÍNTEGRO
Sucede cuando el block_id que ha introducido no se encuentra en el registro local y no se ha pasado un archivo de datos externo. Verifique que el block_id es correcto (puede consultarlo abriendo data/local_registry.json), o use el parámetro --data-file para indicar un archivo JSON con los datos a verificar.
La terminal parece colgada después de arrancar el simulador
No está colgada: está publicando mensajes en silencio. Si quiere ver lo que publica en pantalla, no use "make simulate"; ejecute en su lugar:
python -m src.simulator.sensor_simulator --sensor-id sensor_01 --interval 2

Para detener cualquier componente, pulse Ctrl+C en su terminal.
12. Para profundizar
Este manual cubre lo necesario para instalar, ejecutar y verificar el sistema. Si quiere conocer mejor cómo funciona internamente, los siguientes documentos del proyecto pueden interesarle:
•	Bosquejo de programación: describe la organización interna del código y los criterios de diseño.
•	Marco teórico y metodología (DSRM): expone los fundamentos teóricos y la metodología de investigación.
•	Documento de validación y resultados: presenta las métricas obtenidas y su interpretación.
Para entender mejor las tecnologías subyacentes:
•	IOTA: documentación oficial en https://www.iota.org/, con tutoriales accesibles.
•	SHA-256: explicación técnica en cualquier introducción a criptografía moderna.
•	MQTT: estándar abierto, descrito en https://mqtt.org/.


