import QRCode from 'qrcode';

const INK = '#1E2A2F';

export function qrSvg(url) {
  return QRCode.toString(url, { type: 'svg', margin: 1, color: { dark: INK, light: '#FFFFFF' } });
}

// A large PNG for print (shop window, flyers).
export function qrPngDataUrl(url) {
  return QRCode.toDataURL(url, { width: 1200, margin: 2, color: { dark: INK, light: '#FFFFFF' } });
}
