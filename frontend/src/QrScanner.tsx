import { useEffect, useRef, useState } from 'react'
import { Html5Qrcode } from 'html5-qrcode'

function extractBatchId(raw: string): string | null {
  const text = raw.trim()
  const path = text.match(/\/trace\/([0-9a-fA-F-]{36})/)
  if (path) return path[1]
  const uuid = text.match(/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/)
  return uuid ? uuid[0] : null
}

export function QrScanner({
  onScan,
  onError,
}: {
  onScan: (batchId: string) => void
  onError: (message: string) => void
}) {
  const [active, setActive] = useState(false)
  const scannerRef = useRef<Html5Qrcode | null>(null)
  const regionId = 'qr-reader'

  useEffect(() => {
    return () => {
      const s = scannerRef.current
      if (s?.isScanning) {
        s.stop().catch(() => undefined)
      }
    }
  }, [])

  async function start() {
    onError('')
    try {
      const scanner = new Html5Qrcode(regionId)
      scannerRef.current = scanner
      setActive(true)
      await scanner.start(
        { facingMode: 'environment' },
        { fps: 8, qrbox: { width: 240, height: 240 } },
        (decoded) => {
          const id = extractBatchId(decoded)
          if (!id) {
            onError('QR did not contain a batch id')
            return
          }
          scanner
            .stop()
            .catch(() => undefined)
            .finally(() => {
              scannerRef.current = null
              setActive(false)
              onScan(id)
            })
        },
        () => undefined,
      )
    } catch (err) {
      setActive(false)
      onError(String((err as Error).message ?? err))
    }
  }

  async function stop() {
    const s = scannerRef.current
    if (s?.isScanning) {
      await s.stop().catch(() => undefined)
    }
    scannerRef.current = null
    setActive(false)
  }

  return (
    <div className="stack">
      <div className="row">
        {!active ? (
          <button type="button" className="btn ghost" onClick={start}>
            Scan QR with camera
          </button>
        ) : (
          <button type="button" className="btn ghost" onClick={stop}>
            Stop camera
          </button>
        )}
      </div>
      <div id={regionId} className={active ? 'qr-scan active' : 'qr-scan'} />
    </div>
  )
}
