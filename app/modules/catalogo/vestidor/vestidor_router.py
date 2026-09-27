import asyncio
import base64
import json
import os
import urllib.parse
import uuid

import aiohttp
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.modules.catalogo.vestidor.schemas.vestidor_asset_schema import PrendaARResponse
from app.modules.catalogo.vestidor.schemas.vestidor_sesion_schema import (
    CrearSesionVestidorRequest,
    SesionVestidorResponse,
)
from app.modules.catalogo.vestidor.vestidor_service import (
    obtener_prenda_ar,
    listar_prendas_vestidor,
    guardar_sesion_vestidor,
)

router = APIRouter(
    prefix="/api/v1/catalogo/vestidor",
    tags=["CU24 - Vestidor Virtual con Realidad Aumentada"],
)


@router.get(
    "/prenda/{producto_id}",
    response_model=PrendaARResponse,
    summary="Obtener activos y dimensiones de prenda para vestidor virtual AR",
)
def get_prenda_vestidor(producto_id: int) -> PrendaARResponse:
    return obtener_prenda_ar(producto_id)


@router.get(
    "/prendas-disponibles",
    summary="Listar prendas activas disponibles para el carrusel del vestidor",
)
def get_prendas_carrusel(limite: int = 30) -> list[dict[str, object]]:
    return listar_prendas_vestidor(limite)


@router.post(
    "/sesion",
    response_model=SesionVestidorResponse,
    summary="Registrar trazabilidad de prueba virtual en vestidor",
)
def post_sesion_vestidor(request: CrearSesionVestidorRequest) -> SesionVestidorResponse:
    return guardar_sesion_vestidor(request)


@router.get(
    "/config",
    summary="Configuración del motor de vestidor para la app móvil",
)
def get_vestidor_config() -> dict[str, str]:
    return {
        "engine": "DECART_LUCY_VTON",
        "realtime_supported": "true",
        "model": "lucy-vton-3.5",
    }


# Mapeo en memoria de sesiones WebRTC activas con Decart
ACTIVE_DECART_SESSIONS: dict[str, dict] = {}


async def _keep_decart_alive(session_id: str, ws: aiohttp.ClientWebSocketResponse, session: aiohttp.ClientSession):
    """Mantiene la conexión WebSocket de control con Decart viva en segundo plano."""
    try:
        print(f"[Decart WS Bridge] Iniciando loop de escucha para {session_id}")
        while True:
            msg = await ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                # Mensaje de texto informativo de Decart (session_id, acks, etc.)
                pass
            elif msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.ERROR,
            ):
                print(f"[Decart WS Bridge] Socket cerrado por servidor Decart para {session_id}: {msg.type}")
                break
    except asyncio.CancelledError:
        print(f"[Decart WS Bridge] Tarea cancelada para {session_id}")
    except Exception as e:
        print(f"[Decart WS Bridge] Sesión {session_id} excepción: {e}")
    finally:
        ACTIVE_DECART_SESSIONS.pop(session_id, None)
        try:
            if not ws.closed:
                await ws.close()
            if not session.closed:
                await session.close()
        except Exception:
            pass
        print(f"[Decart WS Bridge] Limpieza de sesión {session_id} finalizada.")


@router.post(
    "/sesion-realtime",
    summary="Crear sesión WebRTC en vivo con Decart Lucy VTON 3.5 (WebSocket persistente)",
)
async def post_sesion_realtime(producto_id: int = 1) -> dict[str, object]:
    from app.modules.catalogo.vestidor.vestidor_ia_service import GARMENT_AI_CONFIG, _get_decart_api_key

    api_key = _get_decart_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="DECART_API_KEY no configurada.")
    api_key = api_key.strip()

    cfg = GARMENT_AI_CONFIG.get(producto_id, GARMENT_AI_CONFIG.get(1, {}))
    img_path = cfg.get("image")
    if not img_path or not os.path.exists(img_path):
        for c in GARMENT_AI_CONFIG.values():
            if os.path.exists(c.get("image", "")):
                img_path = c["image"]
                break

    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    url = f"wss://api3.decart.ai/v1/stream?api_key={urllib.parse.quote(api_key)}&model=lucy-vton-3.5&livekit_early_room_info=true"

    session = aiohttp.ClientSession()
    try:
        ws = await session.ws_connect(url, timeout=aiohttp.ClientTimeout(total=20))
        set_img_msg = {
            "type": "set_image",
            "image_data": img_b64,
            "prompt": "Virtual try-on clothing photorealistic natural fit on human body",
        }
        await ws.send_str(json.dumps(set_img_msg))
        await ws.receive_str()
        await ws.send_str(json.dumps({"type": "livekit_join"}))
        room_info = json.loads(await ws.receive_str())

        session_id = room_info.get("session_id") or str(uuid.uuid4())

        # Mantener el socket vivo en segundo plano para que Decart no desconecte la sala LiveKit
        task = asyncio.create_task(_keep_decart_alive(session_id, ws, session))
        ACTIVE_DECART_SESSIONS[session_id] = {
            "ws": ws,
            "session": session,
            "task": task,
            "producto_id": producto_id,
        }

        return {
            "status": "ok",
            "livekit_url": room_info.get("livekit_url"),
            "token": room_info.get("token"),
            "room_name": room_info.get("room_name"),
            "session_id": session_id,
            "producto_id": producto_id,
        }
    except Exception as e:
        await session.close()
        print(f"[Decart Realtime] Error al conectar sesión: {e}")
        raise HTTPException(status_code=502, detail=f"Error al iniciar streaming Decart: {e}") from e


@router.post(
    "/cambiar-prenda-realtime",
    summary="Cambiar prenda en la sesión WebRTC de Decart en vivo sin reiniciar la cámara",
)
async def post_cambiar_prenda_realtime(session_id: str, producto_id: int) -> dict[str, object]:
    from app.modules.catalogo.vestidor.vestidor_ia_service import GARMENT_AI_CONFIG

    print(f"[Cambiar Prenda] Buscando {session_id}. Sesiones activas: {list(ACTIVE_DECART_SESSIONS.keys())}")
    sess = ACTIVE_DECART_SESSIONS.get(session_id)
    if not sess or not sess.get("ws") or sess["ws"].closed:
        print(f"[Cambiar Prenda] No activa o cerrada. sess={sess is not None}")
        return {"status": "reconnect_needed", "message": "Sesión expirada"}

    cfg = GARMENT_AI_CONFIG.get(producto_id, GARMENT_AI_CONFIG.get(1, {}))
    img_path = cfg.get("image")
    if not img_path or not os.path.exists(img_path):
        for c in GARMENT_AI_CONFIG.values():
            if os.path.exists(c.get("image", "")):
                img_path = c["image"]
                break

    if not img_path or not os.path.exists(img_path):
        return {"status": "error", "message": "Imagen de prenda no encontrada"}

    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    ws = sess["ws"]
    set_img_msg = {
        "type": "set_image",
        "image_data": img_b64,
        "prompt": "Virtual try-on clothing photorealistic natural fit on human body",
    }
    try:
        await ws.send_str(json.dumps(set_img_msg))
    except Exception as e:
        print(f"[Cambiar Prenda] Error al enviar a Decart WS: {e}")
        ACTIVE_DECART_SESSIONS.pop(session_id, None)
        return {"status": "reconnect_needed", "message": f"Conexión perdida con Decart: {e}"}

    sess["producto_id"] = producto_id
    print(f"[Cambiar Prenda] Prenda {producto_id} enviada exitosamente a Decart WS {session_id}")
    return {"status": "ok", "producto_id": producto_id}


@router.post(
    "/pausar-realtime",
    summary="Pausar o cerrar sesión WebRTC de Decart para congelar consumo de créditos",
)
async def post_pausar_realtime(session_id: str) -> dict[str, str]:
    sess = ACTIVE_DECART_SESSIONS.pop(session_id, None)
    if sess:
        try:
            ws = sess.get("ws")
            if ws and not ws.closed:
                await ws.close()
            session = sess.get("session")
            if session and not session.closed:
                await session.close()
            task = sess.get("task")
            if task and not task.done():
                task.cancel()
        except Exception as e:
            print(f"[Pausar Realtime] Error al cerrar: {e}")
    return {"status": "ok", "message": "Sesión pausada"}


@router.get(
    "/en-vivo-view",
    response_class=HTMLResponse,
    summary="Visor interactivo WebRTC 30 FPS para vestidor en vivo con Decart Lucy VTON",
)
def get_en_vivo_view(producto_id: int = 1) -> HTMLResponse:
    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Vestidor en Vivo • Decart AI</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; -webkit-tap-highlight-color: transparent; }}
    body, html {{ width: 100%; height: 100%; background: #000; overflow: hidden; color: #fff; }}
    #videoContainer {{ position: relative; width: 100vw; height: 100vh; overflow: hidden; background: #000; display: flex; align-items: center; justify-content: center; }}
    video {{ position: absolute; max-width: 100vw; max-height: 100vh; object-fit: contain; background: #000; display: block; }}
    .mirror {{ transform: scaleX(-1); }}
    #localVideo {{ z-index: 1; }}
    #remoteVideo {{ z-index: 2; opacity: 0; transition: opacity 0.6s ease-in-out; }}
    #remoteVideo.active {{ opacity: 1; }}
    #statusPill {{ position: absolute; top: 16px; left: 16px; z-index: 10; display: inline-flex; align-items: center; gap: 8px; background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(10px); border: 1px solid rgba(0, 229, 255, 0.5); padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: bold; color: #fff; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }}
    .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #10B981; box-shadow: 0 0 10px #10B981; }}
    .live-dot {{ background: #00E5FF; box-shadow: 0 0 12px #00E5FF; animation: blink 1.2s infinite; }}
    .paused-dot {{ background: #F59E0B; box-shadow: 0 0 10px #F59E0B; }}
    @keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/livekit-client@2.5.9/dist/livekit-client.umd.min.js"></script>
  <script>
    if (typeof LivekitClient === 'undefined') {{
      const s = document.createElement('script');
      s.src = 'https://unpkg.com/livekit-client@2.5.9/dist/livekit-client.umd.min.js';
      document.head.appendChild(s);
    }}
  </script>
</head>
<body>
  <div id="videoContainer" ondblclick="toggleRotation()">
    <video id="localVideo" class="mirror" autoplay playsinline webkit-playsinline muted poster="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"></video>
    <video id="remoteVideo" class="mirror" autoplay playsinline webkit-playsinline muted poster="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" style="display: none;"></video>
    <div id="statusPill">
      <div class="dot" id="statusDot"></div>
      <span id="statusLabel">Iniciando cámara...</span>
    </div>
  </div>

  <script>
    let localStream = null;
    let currentRoom = null;
    let currentProductId = {producto_id};
    let currentSessionId = null;
    let isPaused = false;
    let manualRot = 0;

    const localVideo = document.getElementById('localVideo');
    const remoteVideo = document.getElementById('remoteVideo');
    const statusDot = document.getElementById('statusDot');
    const statusLabel = document.getElementById('statusLabel');

    function applyOrientation(videoEl) {{
      if (!videoEl || !videoEl.videoWidth) return;
      const vw = videoEl.videoWidth;
      const vh = videoEl.videoHeight;
      const isLandscape = vw > vh;
      
      let baseRot = isLandscape ? 90 : 0;
      let totalRot = (baseRot + manualRot) % 360;

      if (totalRot === 90 || totalRot === 270) {{
        videoEl.style.width = '100vh';
        videoEl.style.height = '100vw';
        videoEl.style.maxWidth = 'none';
        videoEl.style.maxHeight = 'none';
        videoEl.style.transform = 'rotate(' + totalRot + 'deg) scaleX(-1)';
        videoEl.style.objectFit = 'contain';
      }} else {{
        videoEl.style.width = '100%';
        videoEl.style.height = '100%';
        videoEl.style.maxWidth = '100vw';
        videoEl.style.maxHeight = '100vh';
        videoEl.style.transform = totalRot === 180 ? 'rotate(180deg) scaleX(-1)' : 'scaleX(-1)';
        videoEl.style.objectFit = 'contain';
      }}
    }}

    window.toggleRotation = function() {{
      manualRot = (manualRot + 90) % 360;
      applyOrientation(localVideo);
      applyOrientation(remoteVideo);
    }};

    async function initCamera() {{
      try {{
        let stream = null;
        try {{
          stream = await navigator.mediaDevices.getUserMedia({{
            audio: false,
            video: {{ facingMode: 'user' }}
          }});
        }} catch (e1) {{
          console.warn('Fallback a video basico:', e1);
          stream = await navigator.mediaDevices.getUserMedia({{
            audio: false,
            video: true
          }});
        }}

        localStream = stream;
        localVideo.srcObject = stream;
        localVideo.muted = true;
        await localVideo.play();
        
        localVideo.onloadedmetadata = () => applyOrientation(localVideo);
        localVideo.onplay = () => applyOrientation(localVideo);
        applyOrientation(localVideo);
        setTimeout(() => applyOrientation(localVideo), 150);
        
        statusLabel.textContent = 'Cámara en Vivo';

        // Iniciar conexión con Decart Lucy VTON WebRTC
        startDecartSession(currentProductId);
      }} catch (err) {{
        console.error('Error cámara:', err);
        statusDot.className = 'dot paused-dot';
        statusLabel.textContent = 'Error cámara: ' + (err.name || err.message || err);
      }}
    }}

    let isConnecting = false;

    async function startDecartSession(productId) {{
      if (isPaused) return;
      if (isConnecting) return;
      isConnecting = true;
      currentProductId = productId;
      statusDot.className = 'dot live-dot';
      statusLabel.textContent = 'Amoldando prenda...';

      try {{
        // Esperar si LivekitClient aún se está descargando desde el CDN
        for (let i = 0; i < 30 && typeof LivekitClient === 'undefined'; i++) {{
          await new Promise(r => setTimeout(r, 100));
        }}
        if (typeof LivekitClient === 'undefined') {{
          throw new Error('WebRTC cargando...');
        }}

        if (currentRoom) {{
          try {{ await currentRoom.disconnect(); }} catch (e) {{}}
          currentRoom = null;
        }}

        // 1. Obtener sesión LiveKit firmada desde el backend
        const res = await fetch('/api/v1/catalogo/vestidor/sesion-realtime?producto_id=' + productId, {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true'
          }}
        }});
        if (!res.ok) {{
          const errText = await res.text();
          throw new Error('Servidor ' + res.status + ': ' + errText.substring(0, 40));
        }}
        const sessionData = await res.json();
        currentSessionId = sessionData.session_id;

        // 2. Conectar a sala LiveKit de Decart (sin forzar resolución landscape)
        const room = new LivekitClient.Room({{
          adaptiveStream: true,
          dynacast: true,
        }});
        currentRoom = room;

        room.on(LivekitClient.RoomEvent.TrackSubscribed, (track) => {{
          if (track.kind === LivekitClient.Track.Kind.Video || track.kind === 'video') {{
            track.attach(remoteVideo);
            remoteVideo.style.display = 'block';
            remoteVideo.muted = true;
            remoteVideo.play().catch(e => console.warn('remote play error:', e));
            remoteVideo.onloadedmetadata = () => applyOrientation(remoteVideo);
            remoteVideo.onplay = () => applyOrientation(remoteVideo);
            applyOrientation(remoteVideo);
            setTimeout(() => applyOrientation(remoteVideo), 200);
            remoteVideo.classList.add('active');
            statusDot.className = 'dot';
            statusDot.style.background = '#10B981';
            statusLabel.textContent = '🔴 En Vivo • Decart Lucy 3.5';
          }}
        }});

        room.on(LivekitClient.RoomEvent.Disconnected, () => {{
          remoteVideo.classList.remove('active');
          remoteVideo.style.display = 'none';
        }});

        await room.connect(sessionData.livekit_url, sessionData.token);

        // 3. Publicar la cámara local para que Decart amolde el video en tiempo real a 30 FPS
        if (localStream) {{
          const videoTrack = localStream.getVideoTracks()[0];
          if (videoTrack) {{
            await room.localParticipant.publishTrack(videoTrack, {{
              name: 'camera',
              source: LivekitClient.Track.Source.Camera,
              simulcast: false
            }});
          }}
        }}

        // 4. Si Decart ya tiene tracks suscritos en la sala, vincularlos inmediatamente
        room.remoteParticipants.forEach((participant) => {{
          participant.trackPublications.forEach((pub) => {{
            if (pub.track && (pub.track.kind === LivekitClient.Track.Kind.Video || pub.track.kind === 'video')) {{
              pub.track.attach(remoteVideo);
              remoteVideo.style.display = 'block';
              remoteVideo.muted = true;
              remoteVideo.play().catch(e => console.warn('remote play:', e));
              remoteVideo.classList.add('active');
              statusDot.className = 'dot';
              statusDot.style.background = '#10B981';
              statusLabel.textContent = '🔴 En Vivo • Decart Lucy 3.5';
            }}
          }});
        }});

      }} catch (e) {{
        console.error('Error Decart Realtime:', e);
        statusDot.className = 'dot paused-dot';
        statusLabel.textContent = 'En Vivo (Cámara) • ' + (e.message || 'Sin IA');
      }} finally {{
        isConnecting = false;
      }}
    }}

    // Métodos globales llamados desde Flutter
    window.pauseLiveStream = function() {{
      isPaused = true;
      if (currentSessionId) {{
        fetch('/api/v1/catalogo/vestidor/pausar-realtime?session_id=' + currentSessionId, {{
          method: 'POST',
          headers: {{ 'ngrok-skip-browser-warning': 'true' }}
        }}).catch(() => {{}});
      }}
      if (currentRoom) {{
        try {{ currentRoom.disconnect(); }} catch (e) {{}}
        currentRoom = null;
      }}
      remoteVideo.classList.remove('active');
      remoteVideo.style.display = 'none';
      statusDot.className = 'dot paused-dot';
      statusLabel.textContent = 'Pausado (0 tokens consumidos)';
    }};

    window.resumeLiveStream = function() {{
      isPaused = false;
      startDecartSession(currentProductId);
    }};

    window.switchGarment = async function(productId) {{
      if (currentProductId === productId && currentRoom && currentSessionId) return;
      currentProductId = productId;
      statusDot.className = 'dot live-dot';
      statusLabel.textContent = 'Amoldando prenda...';

      if (currentRoom && currentSessionId) {{
        try {{
          const res = await fetch('/api/v1/catalogo/vestidor/cambiar-prenda-realtime?session_id=' + currentSessionId + '&producto_id=' + productId, {{
            method: 'POST',
            headers: {{
              'Content-Type': 'application/json',
              'ngrok-skip-browser-warning': 'true'
            }}
          }});
          const data = await res.json();
          if (data.status === 'ok') {{
            statusDot.className = 'dot';
            statusDot.style.background = '#10B981';
            statusLabel.textContent = '🔴 En Vivo • Decart Lucy 3.5';
            return;
          }}
        }} catch (e) {{
          console.warn('Error al cambiar prenda en caliente:', e);
        }}
      }}
      startDecartSession(productId);
    }};

    window.addEventListener('load', initCamera);
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@router.post(
    "/token-en-vivo",
    summary="Generar token efímero de sesión para streaming de vestidor en vivo con Decart AI",
)
def post_token_en_vivo(duracion_segundos: int = 300) -> dict[str, object]:
    from app.modules.catalogo.vestidor.vestidor_ia_service import generar_token_webrtc_decart

    return generar_token_webrtc_decart(duracion_segundos=duracion_segundos)


try:
    import multipart  # noqa: F401
    from fastapi import File, Form, Request, UploadFile

    MULTIPART_DISPONIBLE = True
except ModuleNotFoundError:
    MULTIPART_DISPONIBLE = False


if MULTIPART_DISPONIBLE:

    @router.post(
        "/probar-ia",
        summary="Procesar prueba virtual de prenda sobre foto de usuario con IA",
    )
    async def post_probar_ia(
        request: Request,
        imagen: UploadFile = File(...),
        producto_id: int = Form(...),
        talla: str | None = Form(None),
        color: str | None = Form(None),
        cliente_id: int | None = Form(None),
    ) -> dict[str, object]:
        try:
            from app.modules.catalogo.vestidor.vestidor_ia_service import procesar_tryon_ia
        except ModuleNotFoundError as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "El motor de prueba virtual con IA no tiene sus dependencias "
                    "instaladas. Instala las dependencias del backend y reinicia el servidor."
                ),
            ) from error

        contenido = await imagen.read()
        host_base_url = str(request.base_url).rstrip("/")
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
        if forwarded_host:
            host_base_url = f"{forwarded_proto}://{forwarded_host}"

        return procesar_tryon_ia(
            imagen_bytes=contenido,
            producto_id=producto_id,
            talla=talla,
            color=color,
            cliente_id=cliente_id,
            host_base_url=host_base_url,
        )

else:

    @router.post(
        "/probar-ia",
        summary="Procesar prueba virtual de prenda sobre foto de usuario con IA",
    )
    async def post_probar_ia_no_disponible() -> dict[str, object]:
        raise HTTPException(
            status_code=503,
            detail=(
                "El motor de prueba virtual con IA requiere python-multipart y "
                "sus dependencias de visión. Instala las dependencias del backend "
                "y reinicia el servidor."
            ),
        )

