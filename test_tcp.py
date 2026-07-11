"""发送高振幅测试音频到 TCP 8004"""
import socket, struct, time, math

s = socket.create_connection(('127.0.0.1', 8004), timeout=5)
print("TCP connected")

# 生成 16-bit PCM: 800Hz sine wave at amplitude 8000 (> threshold 350)
amp = 8000
for i in range(1000):
    val = int(math.sin(i * 0.1) * amp)
    sample = struct.pack('<h', val)
    pcm = sample * 480
    frame = b'\x00' + struct.pack('<I', len(pcm)) + pcm
    s.sendall(frame)

s.sendall(b'\x01' + struct.pack('<I', 0))
print("Sent 3s high-amp audio")
time.sleep(8)
s.close()
print("Done")
