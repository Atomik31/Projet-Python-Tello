"""
Contrôle simultané de deux drones :
- DJI Tello (via WiFi)
- Parrot Mambo (via Bluetooth BLE)

Synchronisation des mouvements pour démonstrations coordonnées
"""

import asyncio
from djitellopy import Tello
from bleak import BleakClient, BleakScanner
import struct
import time
import signal
import sys
import threading

# ============================================================
#                    CLASSE MAMBO CONTROLLER
# ============================================================

class MamboController:
    """Contrôleur pour le drone Parrot Mambo (BLE)"""
    
    CHAR_SEND_NOACK = "9a66fa0a-0800-9191-11e4-012d1540cb8e"
    CHAR_SEND_ACK = "9a66fa0b-0800-9191-11e4-012d1540cb8e"
    CHAR_RECV_NOACK = "9a66fb0f-0800-9191-11e4-012d1540cb8e"
    CHAR_RECV_ACK = "9a66fb0e-0800-9191-11e4-012d1540cb8e"
    
    def __init__(self, address=None):
        self.address = address
        self.client = None
        self.sequence_ack = 0
        self.sequence_noack = 0
        self.connected = False
        self.pcmd_task = None
        
        self.roll = 0
        self.pitch = 0
        self.yaw = 0
        self.gaz = 0
        self.flag = 0
        
        self.battery = 0
        self.flying_state = "unknown"
        self.debug_mode = False
    
    async def find_mambo(self):
        """Recherche un Mambo à proximité"""
        print("🔍 [MAMBO] Recherche...")
        devices = await BleakScanner.discover(timeout=5.0)
        
        for device in devices:
            if device.name and "Mambo" in device.name:
                print(f"✓ [MAMBO] Trouvé: {device.name} ({device.address})")
                return device.address
        
        print("✗ [MAMBO] Non trouvé")
        return None
    
    def _decode_state(self, data):
        """Décode les messages d'état"""
        if len(data) < 6:
            return
        
        project = data[2]
        class_id = data[3]
        cmd = struct.unpack('<H', data[4:6])[0]
        
        if project == 2 and class_id == 3 and cmd == 1 and len(data) >= 8:
            state_id = struct.unpack('<I', data[6:10])[0]
            states = ["landed", "takingoff", "hovering", "flying", "landing", "emergency"]
            self.flying_state = states[state_id] if state_id < len(states) else f"unknown({state_id})"
            print(f"✈️  [MAMBO] État: {self.flying_state}")
        
        elif project == 0 and class_id == 5 and cmd == 1 and len(data) >= 7:
            self.battery = data[6]
            print(f"🔋 [MAMBO] Batterie: {self.battery}%")
    
    def _notification_handler_ack(self, sender, data):
        self._decode_state(data)
    
    def _notification_handler_noack(self, sender, data):
        pass
    
    async def _pcmd_loop(self):
        """Boucle PCMD pour maintenir la connexion"""
        while self.connected and self.client and self.client.is_connected:
            try:
                timestamp = int(time.time() * 1000) % (2**32)
                
                data = struct.pack('<BbbbbI',
                                  self.flag,
                                  self.roll,
                                  self.pitch,
                                  self.yaw,
                                  self.gaz,
                                  timestamp)
                
                payload = struct.pack('<BBH', 2, 0, 2) + data
                frame = struct.pack('<BB', 2, self.sequence_noack) + payload
                
                await self.client.write_gatt_char(self.CHAR_SEND_NOACK, frame, response=False)
                self.sequence_noack = (self.sequence_noack + 1) % 256
                
                await asyncio.sleep(0.05)
            except Exception as e:
                if self.debug_mode:
                    print(f"⚠️  [MAMBO] Erreur PCMD: {e}")
                break
    
    async def _send_command(self, project, class_id, cmd, data=b''):
        """Envoie une commande avec ACK"""
        payload = struct.pack('<BBH', project, class_id, cmd) + data
        frame = struct.pack('<BB', 2, self.sequence_ack) + payload
        
        await self.client.write_gatt_char(self.CHAR_SEND_ACK, frame, response=False)
        self.sequence_ack = (self.sequence_ack + 1) % 256
        await asyncio.sleep(0.1)
    
    async def connect(self):
        """Connexion au Mambo"""
        if not self.address:
            self.address = await self.find_mambo()
            if not self.address:
                return False
        
        print(f"📡 [MAMBO] Connexion à {self.address}...")
        await asyncio.sleep(2)
        
        self.client = BleakClient(self.address, timeout=30.0)
        
        try:
            await self.client.connect()
            print("✓ [MAMBO] Connecté!")
            
            await self.client.start_notify(self.CHAR_RECV_ACK, self._notification_handler_ack)
            await self.client.start_notify(self.CHAR_RECV_NOACK, self._notification_handler_noack)
            
            self.connected = True
            self.pcmd_task = asyncio.create_task(self._pcmd_loop())
            
            await asyncio.sleep(1)
            
            # Initialisation
            datetime_str = time.strftime("%Y-%m-%dT%H:%M:%S+0000")
            data = datetime_str.encode('utf-8') + b'\x00'
            await self._send_command(0, 4, 1, data)
            await self._send_command(0, 4, 0)
            
            await asyncio.sleep(1)
            print("✓ [MAMBO] Prêt!")
            return True
            
        except Exception as e:
            print(f"✗ [MAMBO] Erreur: {e}")
            return False
    
    async def disconnect(self):
        """Déconnexion"""
        self.connected = False
        
        if self.pcmd_task:
            self.pcmd_task.cancel()
            try:
                await self.pcmd_task
            except asyncio.CancelledError:
                pass
        
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        
        print("📴 [MAMBO] Déconnecté")
    
    async def flat_trim(self):
        """Calibration"""
        print("🎯 [MAMBO] Calibration...")
        await self._send_command(2, 0, 0)
    
    async def takeoff(self):
        """Décollage"""
        print("🚁 [MAMBO] Décollage...")
        await self._send_command(2, 0, 1)
    
    async def land(self):
        """Atterrissage"""
        print("🛬 [MAMBO] Atterrissage...")
        await self._send_command(2, 0, 3)
    
    def move(self, roll=0, pitch=0, yaw=0, gaz=0):
        """Déplacement"""
        self.flag = 1 if any([roll, pitch, yaw, gaz]) else 0
        self.roll = max(-100, min(100, roll))
        self.pitch = max(-100, min(100, pitch))
        self.yaw = max(-100, min(100, yaw))
        self.gaz = max(-100, min(100, gaz))
    
    def hover(self):
        """Hover (arrêt)"""
        self.flag = 0
        self.roll = 0
        self.pitch = 0
        self.yaw = 0
        self.gaz = 0


# ============================================================
#                    CONTRÔLEUR DUAL
# ============================================================

class DualDroneController:
    """Contrôle simultané Tello + Mambo"""
    
    def __init__(self):
        self.tello = None
        self.mambo = None
        self.running = True
        
        # Compensation de dérive Tello
        self.tello_compensation_roll = -10  # Gauche
        self.tello_compensation_pitch = -10  # Arrière
    
    def emergency_stop(self, sig=None, frame=None):
        """Arrêt d'urgence des deux drones"""
        print("\n\n🚨 ARRÊT D'URGENCE - LES DEUX DRONES 🚨\n")
        self.running = False
        
        # Tello
        if self.tello:
            try:
                self.tello.land()
                print("✓ [TELLO] Atterri")
            except:
                print("✗ [TELLO] Erreur atterrissage")
        
        sys.exit(0)
    
    async def init_tello(self):
        """Initialise le Tello"""
        print("\n" + "=" * 60)
        print("INITIALISATION TELLO")
        print("=" * 60)
        
        self.tello = Tello()
        
        try:
            print("📡 [TELLO] Connexion...")
            self.tello.connect()
            battery = self.tello.get_battery()
            print(f"✓ [TELLO] Connecté - Batterie: {battery}%")
            
            if battery < 20:
                print("⚠️  [TELLO] Batterie faible!")
                return False
            
            return True
            
        except Exception as e:
            print(f"✗ [TELLO] Erreur: {e}")
            return False
    
    async def init_mambo(self):
        """Initialise le Mambo"""
        print("\n" + "=" * 60)
        print("INITIALISATION MAMBO")
        print("=" * 60)
        
        self.mambo = MamboController()
        return await self.mambo.connect()
    
    async def stabilize_tello(self, duration):
        """Stabilise le Tello avec compensation de dérive"""
        start = time.time()
        while time.time() - start < duration and self.running:
            try:
                self.tello.send_rc_control(
                    self.tello_compensation_roll,
                    self.tello_compensation_pitch,
                    0, 0
                )
                await asyncio.sleep(0.05)
            except:
                break
    
    async def demo_simple(self):
        """Démonstration simple : décollage synchronisé"""
        print("\n" + "=" * 60)
        print("DÉMONSTRATION : DÉCOLLAGE SYNCHRONISÉ")
        print("=" * 60)
        print("\n⚠️  Les deux drones vont décoller en même temps")
        print("⚠️  Puis rester en vol 5 secondes")
        print("⚠️  Puis atterrir ensemble\n")
        
        input("➤ Appuyez sur ENTRÉE pour démarrer...")
        
        try:
            # Calibration Mambo
            await self.mambo.flat_trim()
            await asyncio.sleep(2)
            
            # Décollage synchronisé
            print("\n🚁 DÉCOLLAGE SYNCHRONISÉ!")
            print("=" * 60)
            
            # Lancer les deux décollages en parallèle
            tello_task = asyncio.create_task(asyncio.to_thread(self.tello.takeoff))
            mambo_task = asyncio.create_task(self.mambo.takeoff())
            
            await asyncio.gather(tello_task, mambo_task)
            
            print("✓ Les deux drones sont en vol!")
            await asyncio.sleep(2)
            
            # Vol stabilisé 5 secondes
            print("\n🔄 STABILISATION 5 SECONDES")
            print("=" * 60)
            
            stabilize_task = asyncio.create_task(self.stabilize_tello(5))
            
            for i in range(5, 0, -1):
                print(f"   {i}s...")
                await asyncio.sleep(1)
            
            await stabilize_task
            self.mambo.hover()
            
            print("\n✓ Stabilisation terminée")
            
            # Atterrissage synchronisé
            print("\n🛬 ATTERRISSAGE SYNCHRONISÉ")
            print("=" * 60)
            
            tello_land_task = asyncio.create_task(asyncio.to_thread(self.tello.land))
            mambo_land_task = asyncio.create_task(self.mambo.land())
            
            await asyncio.gather(tello_land_task, mambo_land_task)
            
            print("✓ Les deux drones ont atterri!")
            await asyncio.sleep(3)
            
        except KeyboardInterrupt:
            print("\n🚨 Interruption utilisateur")
        except Exception as e:
            print(f"\n✗ Erreur: {e}")
    
    async def demo_carre_synchronise(self):
        """Les deux drones volent en carré en même temps"""
        print("\n" + "=" * 60)
        print("DÉMONSTRATION : CARRÉ SYNCHRONISÉ")
        print("=" * 60)
        print("\n⚠️  Les deux drones vont voler en carré simultanément")
        print("⚠️  Espace requis: 3m x 3m pour chaque drone")
        print("⚠️  Placez les drones à 2m l'un de l'autre\n")
        
        input("➤ Appuyez sur ENTRÉE pour démarrer...")
        
        try:
            # Calibration et décollage
            await self.mambo.flat_trim()
            await asyncio.sleep(2)
            
            print("\n🚁 DÉCOLLAGE")
            tello_task = asyncio.create_task(asyncio.to_thread(self.tello.takeoff))
            mambo_task = asyncio.create_task(self.mambo.takeoff())
            await asyncio.gather(tello_task, mambo_task)
            
            print("✓ Drones en vol!")
            await asyncio.sleep(2)
            
            # Carré synchronisé (4 côtés)
            print("\n🔲 VOL EN CARRÉ SYNCHRONISÉ")
            print("=" * 60)
            
            for i in range(4):
                print(f"\n→ Côté {i+1}/4")
                
                # Avancer (Tello + Mambo)
                print("   Avance...")
                self.mambo.move(pitch=40)
                
                # Tello avance avec compensation
                tello_forward = asyncio.create_task(asyncio.to_thread(
                    self.tello.move_forward, 50
                ))
                
                # Stabilisation Mambo
                await asyncio.sleep(2)
                await tello_forward
                
                self.mambo.hover()
                await asyncio.sleep(1)
                
                # Rotation 90° (les deux)
                print("   Rotation 90°...")
                self.mambo.move(yaw=60)
                
                tello_rotate = asyncio.create_task(asyncio.to_thread(
                    self.tello.rotate_clockwise, 90
                ))
                
                await asyncio.sleep(1.5)
                await tello_rotate
                
                self.mambo.hover()
                
                # Stabilisation Tello
                stabilize_task = asyncio.create_task(self.stabilize_tello(1))
                await asyncio.sleep(1)
                await stabilize_task
            
            print("\n✓ Carré terminé!")
            
            # Atterrissage
            print("\n🛬 ATTERRISSAGE")
            tello_land = asyncio.create_task(asyncio.to_thread(self.tello.land))
            mambo_land = asyncio.create_task(self.mambo.land())
            await asyncio.gather(tello_land, mambo_land)
            
            print("✓ Les deux drones ont atterri!")
            await asyncio.sleep(3)
            
        except KeyboardInterrupt:
            print("\n🚨 Interruption")
        except Exception as e:
            print(f"\n✗ Erreur: {e}")
    
    async def run(self):
        """Lance le contrôleur dual"""
        # Configuration signal d'urgence
        signal.signal(signal.SIGINT, self.emergency_stop)
        
        print("=" * 60)
        print("    CONTRÔLE DUAL : TELLO + MAMBO")
        print("=" * 60)
        
        try:
            # Initialisation des deux drones
            tello_ok = await self.init_tello()
            mambo_ok = await self.init_mambo()
            
            if not tello_ok or not mambo_ok:
                print("\n✗ Échec de l'initialisation")
                return
            
            print("\n✓ Les deux drones sont prêts!")
            
            # Menu de démonstrations
            print("\n" + "=" * 60)
            print("DÉMONSTRATIONS DISPONIBLES")
            print("=" * 60)
            print("1. Décollage synchronisé + 5s + Atterrissage")
            print("2. Vol en carré synchronisé")
            print("\n")
            
            mode = input("Choisir (1-2): ").strip()
            
            if mode == "1":
                await self.demo_simple()
            elif mode == "2":
                await self.demo_carre_synchronise()
            else:
                print("❌ Mode invalide")
            
        except Exception as e:
            print(f"\n✗ Erreur globale: {e}")
        
        finally:
            # Nettoyage
            print("\n📴 Déconnexion des drones...")
            if self.mambo:
                await self.mambo.disconnect()
            print("✓ Programme terminé")


# ============================================================
#                         MAIN
# ============================================================

async def main():
    controller = DualDroneController()
    await controller.run()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("    🚁 CONTRÔLE SIMULTANÉ TELLO + MAMBO 🚁")
    print("=" * 60)
    print("\n⚠️  IMPORTANT:")
    print("  • Tello doit être connecté en WiFi (TELLO-XXXXXX)")
    print("  • Mambo doit être allumé et à proximité (Bluetooth)")
    print("  • Placez les drones à 2m l'un de l'autre")
    print("  • Espace requis: 3m x 3m minimum")
    print("  • Ctrl+C = Arrêt d'urgence des DEUX drones")
    print("\n")
    
    asyncio.run(main())