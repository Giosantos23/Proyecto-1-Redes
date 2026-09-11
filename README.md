# Proyecto-1-Redes

Este repositorio contiene la implementación de un chatbot en línea de comandos que interactúa con el mundo real utilizando el Model Context Protocol (MCP). El proyecto aborda la integración de un Modelo de Lenguaje Grande (LLM) con herramientas externas mediante el intercambio manual de mensajes JSON-RPC 2.0, operando tanto a nivel de procesos locales (stdio) como a través de red (HTTP/SSE).  
El caso de uso a nivel industrial es un Asistente de Recursos Humanos, el cual facilita a empleados sin conocimientos técnicos la consulta de directorios, saldos de vacaciones y el registro de ausencias mediante lenguaje natural.  


### Funcionamiento
- Conexión a LLM a nivel de API: Integración directa con Google Gemini (gemini-3.5-flash-lite) para procesar el lenguaje natural y coordinar el uso de herramientas.
- Mantenimiento de Contexto: El agente es capaz de recordar información de mensajes anteriores durante toda la sesión de terminal.
- Registro de Auditoría (Logging): Todas las interacciones JSON-RPC (solicitudes, notificaciones y respuestas) entre el anfitrión y los servidores se registran detalladamente en el archivo logs/mcp_interactions.jsonl

### Instalación

`git clone https://github.com/Giosantos23/Proyecto-1-Redes.git
cd Proyecto-1-Redes`

`python3 -m venv .venv
source .venv/bin/activate`

`python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt`

### Instrucciones de uso
#### Interacción con servidor local
`python3 -m chatbot.main`
- Ejemplo de uso: Escriba `"¿Cuántos días de vacaciones tiene Ana para el año 2026?". El LLM descubrirá la herramienta, enviará los parámetros y mostrará el saldo disponible.

#### Interacción con Servidores GIT y Filesystem
`python3 -m chatbot.main --with-official`
- Ejemplo de uso: Escriba `"Crea un archivo llamado notas.md en el directorio de demostración, escribe un título breve y luego haz un commit en Git"*.

#### Interacción con servidor remoto
`HR_REMOTE_URL=https://proyecto-1-redes.onrender.com python3 -m chatbot.main`
