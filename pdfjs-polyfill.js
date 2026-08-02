// PDF.js 兼容 polyfill (旧内核: 补 ES2022~2024 API)
if (!Promise.withResolvers) {
  Promise.withResolvers = function () {
    let resolve, reject;
    const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
  };
}
if (!URL.parse) {
  URL.parse = function (url, base) {
    try { return new URL(url, base); } catch (e) { return null; }
  };
}
if (!Array.prototype.at) {
  Array.prototype.at = function (n) {
    n = Math.trunc(n) || 0;
    if (n < 0) n += this.length;
    return n < 0 || n >= this.length ? undefined : this[n];
  };
}
if (!Array.prototype.findLast) {
  Array.prototype.findLast = function (fn, thisArg) {
    for (let i = this.length - 1; i >= 0; i--) {
      if (fn.call(thisArg, this[i], i, this)) return this[i];
    }
    return undefined;
  };
}
if (!Array.prototype.findLastIndex) {
  Array.prototype.findLastIndex = function (fn, thisArg) {
    for (let i = this.length - 1; i >= 0; i--) {
      if (fn.call(thisArg, this[i], i, this)) return i;
    }
    return -1;
  };
}
if (typeof structuredClone !== 'function') {
  globalThis.structuredClone = function (val) {
    if (val === null || typeof val !== 'object') return val;
    return JSON.parse(JSON.stringify(val));
  };
}
