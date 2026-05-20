from machine import Pin, PWM
import time
import network
import socket
import select
import random

# --- Configuración de Componentes ---
# Teclado
keys = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D']
]
row_pins = [Pin(13, Pin.OUT), Pin(12, Pin.OUT), Pin(14, Pin.OUT), Pin(27, Pin.OUT)]
col_pins = [Pin(26, Pin.IN, Pin.PULL_UP), Pin(25, Pin.IN, Pin.PULL_UP), Pin(33, Pin.IN, Pin.PULL_UP),
            Pin(32, Pin.IN, Pin.PULL_UP)]

for row in row_pins:
    row.value(1)

# Servo
servo = PWM(Pin(15), freq=50)

# Buzzer Pasivo
buzzer = PWM(Pin(4))
buzzer.duty_u16(0)  # Iniciar en silencio

# --- WiFi AP Config ---
SSID_AP = 'Cerradura-Admin'
PWD_AP = '12345678'

# --- Funciones de Sonido ---
def tocar_tono(frecuencia, duracion_ms):
    if frecuencia > 0:
        buzzer.freq(frecuencia)
        buzzer.duty_u16(32768)  # 50% de volumen
    time.sleep_ms(duracion_ms)
    buzzer.duty_u16(0)  # Apagar


def sonido_tecla():
    tocar_tono(2000, 50)  # Clic agudo y muy corto


def sonido_exito():
    # Tonos ascendentes
    tocar_tono(1000, 100)
    time.sleep_ms(20)
    tocar_tono(1500, 100)
    time.sleep_ms(20)
    tocar_tono(2000, 200)


def sonido_error():
    tocar_tono(200, 400)  # Tono grave y largo


def sonido_modo_cambio():
    # Dos pitidos medios
    tocar_tono(800, 100)
    time.sleep_ms(50)
    tocar_tono(800, 100)


def sonido_guardado():
    # Tres pitidos rápidos
    tocar_tono(2500, 80)
    time.sleep_ms(40)
    tocar_tono(2500, 80)
    time.sleep_ms(40)
    tocar_tono(2500, 150)


# --- Funciones de Hardware ---
def read_key():
    for i, row in enumerate(row_pins):
        row.value(0)
        for j, col in enumerate(col_pins):
            if col.value() == 0:
                row.value(1)
                sonido_tecla()  # <-- El buzzer suena justo al detectar la tecla
                time.sleep(0.25)  # Antirrebote
                return keys[i][j]
        row.value(1)
    return None


def move_servo(angle):
    min_duty = 1638
    max_duty = 8192
    duty = int(min_duty + (max_duty - min_duty) * angle / 180)
    servo.duty_u16(duty)


# --- Memoria Flash ---
ARCHIVO_PWD = 'pwd.txt'
ARCHIVO_ADMIN = 'admin.txt'


def cargar_password():
    try:
        with open(ARCHIVO_PWD, 'r') as f:
            return f.read().strip()
    except OSError:
        pwd_por_defecto = "1234"
        guardar_password(pwd_por_defecto)
        return pwd_por_defecto


def guardar_password(nueva_pwd):
    with open(ARCHIVO_PWD, 'w') as f:
        f.write(nueva_pwd)


def cargar_admin_password():
    try:
        with open(ARCHIVO_ADMIN, 'r') as f:
            return f.read().strip()
    except OSError:
        pwd_por_defecto = "1234"
        guardar_admin_password(pwd_por_defecto)
        return pwd_por_defecto


def guardar_admin_password(nueva_pwd):
    with open(ARCHIVO_ADMIN, 'w') as f:
        f.write(nueva_pwd)


# --- WiFi AP Setup ---
def iniciar_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=SSID_AP, password=PWD_AP, authmode=network.AUTH_WPA_WPA2_PSK)
    # Configurar IP fija
    ap.ifconfig(('192.168.4.1', '255.255.255.0', '192.168.4.1', '8.8.8.8'))
    print('AP iniciado. SSID:', SSID_AP)
    print('IP:', ap.ifconfig()[0])
    return ap


# --- Estado Inicial ---
password_actual = cargar_password()
admin_password = cargar_admin_password()
buffer_teclas = ""
modo = "NORMAL"
active_session = None
servo_angle = 90

move_servo(90)
buzzer.duty_u16(0)
print("Sistema listo. Contraseña cargada.")

# --- Servidor Web ---
HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin Cerradura</title>
<style>
body{font-family:sans-serif;text-align:center;background:#1a1a2e;color:#eee;margin:0;padding:20px}
.container{max-width:400px;margin:auto;background:#16213e;padding:20px;border-radius:10px;box-shadow:0 0 10px #0f3460}
input,button{width:90%;padding:12px;margin:8px 0;border:none;border-radius:5px;font-size:16px}
button{background:#e94560;color:#fff;font-weight:bold;cursor:pointer}
button.green{background:#0f0;color:#000}
button.red{background:#f00}
#msg{margin-top:10px;color:#ff0;font-weight:bold}
hr{border:0;border-top:1px solid #0f3460;margin:20px 0}
</style>
</head>
<body>
<div class="container" id="login">
<h2>Admin Cerradura</h2>
<input type="text" id="user" placeholder="Usuario" value="admin"><br>
<input type="password" id="pass" placeholder="Contrasena"><br>
<button onclick="login()">Ingresar</button>
<p id="msg"></p>
</div>
<div class="container" id="panel" style="display:none">
<h2>Panel de Control</h2>
<p>Puerta: <span id="status">Cerrada</span></p>
<button class="green" onclick="ctrl('open')">Abrir Puerta</button>
<button class="red" onclick="ctrl('close')">Cerrar Puerta</button>
<hr>
<h3>Cambiar Clave Teclado</h3>
<input type="password" id="newPwd" placeholder="Nueva clave teclado"><br>
<button onclick="change('change_password','newPwd')">Guardar Clave Teclado</button>
<hr>
<h3>Cambiar Clave Admin</h3>
<input type="password" id="newAdmin" placeholder="Nueva clave admin"><br>
<button onclick="change('change_admin_password','newAdmin')">Guardar Clave Admin</button>
<p id="msg2"></p>
</div>
<script>
function getCookie(name){let c=document.cookie.match('(^|;) ?'+name+'=([^;]*)(;|$)');return c?c[2]:'';}
if(getCookie('session')){document.getElementById('login').style.display='none';document.getElementById('panel').style.display='block';}
async function login(){
  let u=document.getElementById('user').value;
  let p=document.getElementById('pass').value;
  let r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'username='+encodeURIComponent(u)+'&password='+encodeURIComponent(p)});
  let t=await r.text();
  if(t=='OK'){document.getElementById('msg').innerText='Bienvenido'; setTimeout(()=>location.reload(),500);}
  else{document.getElementById('msg').innerText='Credenciales incorrectas';}
}
async function ctrl(a){
  let r=await fetch('/api/'+a,{method:'POST'});
  let t=await r.text();
  document.getElementById('msg2').innerText=t;
  if(a=='open')document.getElementById('status').innerText='Abierta';
  if(a=='close')document.getElementById('status').innerText='Cerrada';
}
async function change(ep,id){
  let r=await fetch('/api/'+ep,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'new_password='+encodeURIComponent(document.getElementById(id).value)});
  let t=await r.text();
  document.getElementById('msg2').innerText=t;
}
</script>
</body>
</html>"""


def start_server():
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setblocking(False)
    s.bind(addr)
    s.listen(1)
    print('Servidor escuchando en', addr)
    return s


def generate_token():
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(chars[random.randint(0, len(chars)-1)] for _ in range(16))


def check_auth(request_str):
    global active_session
    if active_session is None:
        return False
    return ('session=' + active_session) in request_str


def parse_form(body):
    params = {}
    if not body:
        return params
    for pair in body.split('&'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            params[k] = v.replace('+', ' ')
    return params


def send_response(client, code, content_type, body, extra_headers=None):
    headers = 'HTTP/1.1 %s\r\nContent-Type: %s\r\nConnection: close\r\n' % (code, content_type)
    if extra_headers:
        headers += extra_headers + '\r\n'
    headers += '\r\n'
    client.send(headers.encode() + body.encode())


def handle_client(client):
    global active_session, password_actual, admin_password, modo, buffer_teclas, servo_angle
    try:
        client.settimeout(0.5)
        request = b""
        # Leer header
        while b"\r\n\r\n" not in request:
            chunk = client.recv(1024)
            if not chunk:
                break
            request += chunk

        if not request:
            client.close()
            return

        header_end = request.find(b"\r\n\r\n")
        header = request[:header_end]
        body = request[header_end+4:]

        header_lines = header.decode().split('\r\n')
        if not header_lines:
            client.close()
            return

        first = header_lines[0].split()
        if len(first) < 2:
            client.close()
            return
        method = first[0]
        path = first[1]

        content_length = 0
        for line in header_lines[1:]:
            if line.lower().startswith('content-length:'):
                content_length = int(line.split(':', 1)[1].strip())
                break

        # Leer resto del body si falta
        while len(body) < content_length:
            chunk = client.recv(1024)
            if not chunk:
                break
            body += chunk
        body_str = body.decode() if body else ""

        request_str = request.decode()

        if method == 'GET' and path == '/':
            send_response(client, '200 OK', 'text/html', HTML_PAGE)

        elif method == 'POST' and path == '/login':
            params = parse_form(body_str)
            u = params.get('username', '')
            p = params.get('password', '')
            if u == 'admin' and p == admin_password:
                token = generate_token()
                active_session = token
                send_response(client, '200 OK', 'text/plain', 'OK',
                              'Set-Cookie: session=%s; Path=/; Max-Age=3600' % token)
            else:
                send_response(client, '403 Forbidden', 'text/plain', 'ERROR')

        elif method == 'POST' and path.startswith('/api/'):
            if not check_auth(request_str):
                send_response(client, '401 Unauthorized', 'text/plain', 'NO_AUTH')
                client.close()
                return

            if path == '/api/open':
                print("Web: Abriendo...")
                move_servo(179)
                servo_angle = 179
                sonido_exito()
                send_response(client, '200 OK', 'text/plain', 'Puerta abierta')

            elif path == '/api/close':
                print("Web: Cerrando...")
                move_servo(90)
                servo_angle = 90
                send_response(client, '200 OK', 'text/plain', 'Puerta cerrada')

            elif path == '/api/change_password':
                params = parse_form(body_str)
                new_pwd = params.get('new_password', '')
                if len(new_pwd) > 0:
                    password_actual = new_pwd
                    guardar_password(password_actual)
                    send_response(client, '200 OK', 'text/plain', 'Clave teclado actualizada')
                else:
                    send_response(client, '400 Bad Request', 'text/plain', 'Clave vacia')

            elif path == '/api/change_admin_password':
                params = parse_form(body_str)
                new_pwd = params.get('new_password', '')
                if len(new_pwd) > 0:
                    admin_password = new_pwd
                    guardar_admin_password(admin_password)
                    send_response(client, '200 OK', 'text/plain', 'Clave admin actualizada')
                else:
                    send_response(client, '400 Bad Request', 'text/plain', 'Clave vacia')
            else:
                send_response(client, '404 Not Found', 'text/plain', 'NOT_FOUND')
        else:
            send_response(client, '404 Not Found', 'text/plain', 'NOT_FOUND')
    except Exception as e:
        print('Error cliente:', e)
    finally:
        try:
            client.close()
        except:
            pass


# Iniciar AP y Servidor
ap = iniciar_ap()
server_sock = start_server()

poller = select.poll()
poller.register(server_sock, select.POLLIN)

# --- Bucle Principal ---
while True:
    # Revisar conexiones web (timeout 20ms para no bloquear teclado)
    events = poller.poll(20)
    for sock, event in events:
        if sock is server_sock:
            try:
                client_sock, addr = server_sock.accept()
                handle_client(client_sock)
            except Exception as e:
                print('Error accept:', e)

    # Lógica del teclado
    key = read_key()

    if key is not None:
        print("Tecla:", key, "| Modo:", modo)

        # ---------------- MODO NORMAL ----------------
        if modo == "NORMAL":
            if key in '0123456789':
                buffer_teclas += key

            elif key == 'A':
                if buffer_teclas == password_actual:
                    print("Abriendo...")
                    move_servo(179)
                    servo_angle = 179
                    sonido_exito()
                else:
                    print("Clave incorrecta.")
                    sonido_error()
                buffer_teclas = ""

            elif key == 'B':
                print("Cerrando...")
                move_servo(90)
                servo_angle = 90
                buffer_teclas = ""

            elif key == 'C':
                buffer_teclas = ""

            elif key == '*':
                modo = "CAMBIO_AUTH"
                buffer_teclas = ""
                print("MODO CAMBIO: Ingresa clave ACTUAL")
                sonido_modo_cambio()

        # ---------------- MODO CAMBIO (AUTORIZACIÓN) ----------------
        elif modo == "CAMBIO_AUTH":
            if key in '0123456789':
                buffer_teclas += key

            elif key == 'A':
                if buffer_teclas == password_actual:
                    modo = "CAMBIO_NUEVA"
                    buffer_teclas = ""
                    print("AUTORIZADO: Ingresa NUEVA clave")
                    sonido_modo_cambio()  # Suena para confirmar el paso
                else:
                    modo = "NORMAL"
                    buffer_teclas = ""
                    print("Error: Clave actual incorrecta.")
                    sonido_error()

            elif key == 'C':
                modo = "NORMAL"
                buffer_teclas = ""
                sonido_error()  # Lo usamos como sonido de cancelación

        # ---------------- MODO CAMBIO (NUEVA CLAVE) ----------------
        elif modo == "CAMBIO_NUEVA":
            if key in '0123456789':
                buffer_teclas += key

            elif key == 'A':
                if len(buffer_teclas) > 0:
                    password_actual = buffer_teclas
                    guardar_password(password_actual)
                    modo = "NORMAL"
                    buffer_teclas = ""
                    print("¡Éxito! Nueva clave guardada.")
                    sonido_guardado()
                else:
                    sonido_error()

            elif key == 'C':
                modo = "NORMAL"
                buffer_teclas = ""
                sonido_error()
