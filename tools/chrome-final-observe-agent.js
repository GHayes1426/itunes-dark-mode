'use strict';

const exe = Process.getModuleByName('iTunes.exe');
const gd = Process.getModuleByName('gdiplus.dll');
const drawAddress = ptr('__DRAW_ADDRESS__');
const directAttach = Interceptor.attach.bind(Interceptor);
const fills = [];
const texts = [];
let active = 0;
let callbacks = 0;
let stopping = false;
let removed = false;
let phase = 'initial';
const native = (name, ret, args) => new NativeFunction(gd.getExportByName(name), ret, args, { traps: 'none' });
const getColor = native('GdipGetSolidFillColor', 'int', ['pointer', 'pointer']);
const createMatrix = native('GdipCreateMatrix', 'int', ['pointer']);
const deleteMatrix = native('GdipDeleteMatrix', 'int', ['pointer']);
const getWorld = native('GdipGetWorldTransform', 'int', ['pointer', 'pointer']);
const getElements = native('GdipGetMatrixElements', 'int', ['pointer', 'pointer']);
const floats = (p, n) => Array.from({ length: n }, (_, i) => p.add(i * 4).readFloat());
function matrix(graphics) {
  const out = Memory.alloc(8), buf = Memory.alloc(24);
  if (createMatrix(out) !== 0) return null;
  const m = out.readPointer();
  try { if (getWorld(graphics, m) || getElements(m, buf)) return null; return floats(buf, 6); }
  finally { deleteMatrix(m); }
}
function loc(address) { const m = Process.findModuleByAddress(address); return { module: m ? m.name : null, rva: m ? address.sub(m.base).toString() : null }; }
function method(o, slot, ret, args) { return new NativeFunction(o.readPointer().add(slot * 8).readPointer(), ret, args, { traps: 'none' }); }
function release(o) { method(o, 2, 'uint', ['pointer'])(o); }
const iidSolid = Memory.alloc(16);
iidSolid.writeByteArray([0xa9, 6, 0xd9, 0x2c, 0xe2, 0x12, 0xdc, 0x11, 0x9f, 0xed, 0, 0x11, 0x43, 0xa0, 0x55, 0xf9]);
function d2dColor(brush) {
  const out = Memory.alloc(8);
  if (method(brush, 0, 'int', ['pointer', 'pointer', 'pointer'])(brush, iidSolid, out) < 0) return null;
  const solid = out.readPointer();
  try { const rgba = Memory.alloc(16); method(solid, 9, 'void', ['pointer', 'pointer'])(solid, rgba); return floats(rgba, 4); }
  finally { release(solid); }
}
function trackEnter() { callbacks++; if (stopping) { callbacks--; return false; } active++; return true; }
function trackLeave(tracked) { callbacks++; if (tracked) active--; callbacks--; }
const gdiHook = Interceptor.attach(gd.getExportByName('GdipFillRectangle'), {
  onEnter(args) {
    this.tracked = trackEnter();
    try {
      if (!this.tracked || fills.length >= 80 || !this.returnAddress.equals(exe.base.add(0xb366d3))) return;
      const rect = Array.from({ length: 4 }, (_, i) => this.context.rdi.add(i * 8).readDouble());
      const transform = matrix(args[0]); if (!transform) return;
      const device = [rect[0] + transform[4], rect[1] + transform[5], rect[0] + rect[2] + transform[4], rect[1] + rect[3] + transform[5]];
      if (device[1] >= 180) return;
      const color = Memory.alloc(4), status = getColor(args[1], color);
      fills.push({ phase, caller: loc(this.returnAddress), rect, transform, device, argb: status === 0 ? '0x' + color.readU32().toString(16) : null });
    } catch (e) { send({ kind: 'error', where: 'gdi', message: String(e) }); }
    finally { callbacks--; }
  },
  onLeave() { trackLeave(this.tracked); }
});
const d2dHook = Interceptor.attach(drawAddress, {
  onEnter(args) {
    this.tracked = trackEnter();
    try {
      if (!this.tracked || texts.length >= 100 || !this.returnAddress.equals(exe.base.add(0xb3c42e))) return;
      const transformBuffer = Memory.alloc(32); method(args[0], 31, 'void', ['pointer', 'pointer'])(args[0], transformBuffer);
      const transform = floats(transformBuffer, 6), rect = floats(args[4], 4);
      const device = [rect[0] + transform[4], rect[1] + transform[5], rect[2] + transform[4], rect[3] + transform[5]];
      if (device[1] >= 180) return;
      texts.push({ phase, caller: loc(this.returnAddress), text: args[1].readUtf16String(Math.min(args[2].toUInt32(), 96)), rect, transform, device, rgba: d2dColor(args[5]), options: args[6].toUInt32() });
    } catch (e) { send({ kind: 'error', where: 'd2d', message: String(e) }); }
    finally { callbacks--; }
  },
  onLeave() { trackLeave(this.tracked); }
});
function mark(value) { phase = value; fills.length = 0; texts.length = 0; return status(); }
function report() { return { fills, texts }; }
function status() { return { active, callbacks, stopping, removed, fillCount: fills.length, textCount: texts.length, drawAddress: drawAddress.toString() }; }
function beginstop() { stopping = true; return status(); }
function remove() { if (!stopping || active || callbacks) return status(); if (!removed) { gdiHook.detach(); d2dHook.detach(); Interceptor.flush(); removed = true; } return status(); }
rpc.exports = { mark, report, status, beginstop, remove };
