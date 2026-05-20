from machine import Pin, PWM
import time

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


# --- Estado Inicial ---
password_actual = cargar_password()
buffer_teclas = ""
modo = "NORMAL"

move_servo(90)
buzzer.duty_u16(0)
print(f"Sistema listo. Contraseña cargada.")

# --- Bucle Principal ---
while True:
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
                    sonido_exito()
                else:
                    print("Clave incorrecta.")
                    sonido_error()
                buffer_teclas = ""

            elif key == 'B':
                print("Cerrando...")
                move_servo(90)
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