import socket
import cv2
import time
import threading

print("=" * 60)
print("  CONTRÔLE MANUEL DJI TELLO - TYPE FPS")
print("=" * 60)

command_socket = None
socket_lock = threading.Lock()

def init_socket():
    global command_socket
    command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    command_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    command_socket.bind(('', 9000))
    command_socket.settimeout(2)

def send_command(command, tello_address=('192.168.10.1', 8889), wait_response=True):
    global command_socket
    with socket_lock:
        try:
            command_socket.sendto(command.encode('utf-8'), tello_address)
            if wait_response:
                try:
                    response, _ = command_socket.recvfrom(1024)
                    return response.decode('utf-8').strip()
                except socket.timeout:
                    return None
            return None
        except Exception as e:
            print(f"Erreur: {e}")
            return None

init_socket()

print("\n1. Connexion au Tello...")
response = send_command('command')
print(f"   Réponse: {response}")

battery = send_command('battery?')
print(f"\n2. Batterie: {battery}%")

if not battery:
    print("⚠️  Erreur de connexion")
    exit(1)

print("\n3. Démarrage du flux vidéo...")
send_command('streamoff')
time.sleep(1)
send_command('streamon')
time.sleep(3)

print("\n4. Ouverture du flux...")
cap = cv2.VideoCapture('udp://0.0.0.0:11111', cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

print("   Attente du flux vidéo...")
for i in range(30):
    ret, frame = cap.read()
    if ret and frame is not None:
        print("   ✓ Flux vidéo OK !")
        break
    time.sleep(0.2)

print("\n" + "=" * 60)
print("COMMANDES (TYPE FPS):")
print("  A=Decoller W=Atterrir Z=Avancer S=Reculer")
print("  Q=Gauche D=Droite ESPACE=Monter C=Descendre")
print("  E=RotDroite R=RotGauche P=Stop ESC=Quitter")
print("=" * 60 + "\n")

speed = 50
flying = False
taking_off = False
landing = False
frame_count = 0
current_battery = battery
left_right_velocity = 0
for_back_velocity = 0
up_down_velocity = 0
yaw_velocity = 0
takeoff_start_time = 0

try:
    print("✓ Système prêt\n")
    
    while True:
        ret, frame = cap.read()
        
        if ret and frame is not None:
            frame_count += 1
            frame = cv2.resize(frame, (960, 720))
            
            if frame_count % 100 == 0:
                bat = send_command('battery?')
                if bat:
                    current_battery = bat
            
            try:
                battery_int = int(current_battery)
                if battery_int > 50:
                    battery_color = (0, 255, 0)
                elif battery_int > 20:
                    battery_color = (0, 165, 255)
                else:
                    battery_color = (0, 0, 255)
            except:
                battery_color = (255, 255, 255)
            
            overlay = frame.copy()
            cv2.rectangle(overlay, (5, 5), (550, 400), (0, 0, 0), -1)
            frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
            
            cv2.putText(frame, "CONTROLE FPS", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(frame, f"Batterie: {current_battery}%", (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.0, battery_color, 3)
            
            # Gérer la transition automatique après décollage
            if taking_off and (time.time() - takeoff_start_time > 3):
                flying = True
                taking_off = False
                print("✓ En vol - Contrôle activé !")
            
            if taking_off:
                status, status_color = "DECOLLAGE...", (0, 255, 255)
            elif landing:
                status, status_color = "ATTERRISSAGE...", (0, 255, 255)
            elif flying:
                status, status_color = "EN VOL", (0, 255, 0)
            else:
                status, status_color = "AU SOL", (128, 128, 128)
            
            cv2.putText(frame, f"Status: {status}", (15, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2)
            cv2.putText(frame, f"Avant/Arriere: {for_back_velocity:>4}", (15, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(frame, f"Gauche/Droite: {left_right_velocity:>4}", (15, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(frame, f"Haut/Bas:      {up_down_velocity:>4}", (15, 205), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(frame, f"Rotation:      {yaw_velocity:>4}", (15, 235), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            cv2.line(frame, (15, 250), (535, 250), (100, 100, 100), 2)
            
            y = 275
            cv2.putText(frame, "COMMANDES:", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            y += 30
            cv2.putText(frame, "A=Decoller  W=Atterrir  ESC=Quitter", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            y += 25
            cv2.putText(frame, "ZQSD=Deplacer  ESPACE=Monter  C=Descendre", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            y += 25
            cv2.putText(frame, "E=Rotation Droite  R=Rotation Gauche", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            y += 25
            cv2.putText(frame, "P=Stop", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
            
            cv2.imshow("Tello - Controle FPS", frame)
        
        key = cv2.waitKey(10) & 0xFF
        
        left_right_velocity = 0
        for_back_velocity = 0
        up_down_velocity = 0
        yaw_velocity = 0
        
        if (key == ord('a') or key == ord('A')) and not flying and not taking_off:
            print("🚁 Décollage en cours...")
            taking_off = True
            takeoff_start_time = time.time()
            
            # Thread pour envoyer la commande takeoff sans bloquer
            def takeoff_thread():
                send_command('takeoff')
            
            threading.Thread(target=takeoff_thread, daemon=True).start()
        
        elif (key == ord('w') or key == ord('W')) and flying and not landing:
            print("🛬 Atterrissage en cours...")
            landing = True
            
            def land_thread():
                global flying, landing
                send_command('rc 0 0 0 0', wait_response=False)
                time.sleep(0.3)
                send_command('land')
                time.sleep(3)
                flying = False
                landing = False
                print("✓ Au sol !")
            
            threading.Thread(target=land_thread, daemon=True).start()
        
        elif key == 27:
            print("\n⚠️  Sortie...")
            if flying or taking_off:
                print("🛬 Atterrissage automatique...")
                send_command('rc 0 0 0 0', wait_response=False)
                time.sleep(0.3)
                send_command('land')
                time.sleep(3)
            break
        
        # Contrôles actifs même pendant le décollage (après 1 seconde)
        if (flying or (taking_off and time.time() - takeoff_start_time > 1)) and not landing:
            if key == ord('z') or key == ord('Z'):
                for_back_velocity = speed
            elif key == ord('s') or key == ord('S'):
                for_back_velocity = -speed
            elif key == ord('q') or key == ord('Q'):
                left_right_velocity = -speed
            elif key == ord('d') or key == ord('D'):
                left_right_velocity = speed
            elif key == 32:
                up_down_velocity = speed
            elif key == ord('c') or key == ord('C'):
                up_down_velocity = -speed
            elif key == ord('e') or key == ord('E'):
                yaw_velocity = speed
            elif key == ord('r') or key == ord('R'):
                yaw_velocity = -speed
            elif key == ord('p') or key == ord('P'):
                left_right_velocity = 0
                for_back_velocity = 0
                up_down_velocity = 0
                yaw_velocity = 0
                print("⏸️  STOP")
        
        # Envoyer les commandes RC
        if (flying or (taking_off and time.time() - takeoff_start_time > 1)) and not landing:
            send_command(f'rc {left_right_velocity} {for_back_velocity} {up_down_velocity} {yaw_velocity}', wait_response=False)

except KeyboardInterrupt:
    print("\n\n⚠️ ARRÊT D'URGENCE")
    if flying or taking_off:
        send_command('rc 0 0 0 0', wait_response=False)
        time.sleep(0.3)
        send_command('land')
        time.sleep(3)

finally:
    send_command('rc 0 0 0 0', wait_response=False)
    cap.release()
    send_command('streamoff', wait_response=False)
    if command_socket:
        command_socket.close()
    cv2.destroyAllWindows()
    print("\n✓ Programme terminé")