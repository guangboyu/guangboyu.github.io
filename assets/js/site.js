/* Theme toggle. The initial value is applied inline in <head> so there is no flash. */
(function () {
  var root = document.documentElement;
  var button = document.querySelector('[data-theme-toggle]');
  if (!button) return;

  function current() {
    var set = root.getAttribute('data-theme');
    if (set) return set;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  button.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch (e) {}
  });
})();

/* Contents on the right of a post: mark the section being read, and keep that
   link in view when the list is taller than the window. */
(function () {
  var nav = document.querySelector('.side-toc');
  if (!nav || !window.requestAnimationFrame) return;
  var box = nav.parentElement;
  var items = [];
  Array.prototype.forEach.call(nav.querySelectorAll('a[href^="#"]'), function (a) {
    var el = document.getElementById(decodeURIComponent(a.hash.slice(1)));
    if (el) items.push({ a: a, el: el });
  });
  if (!items.length) return;

  var current = null, queued = false;
  function update() {
    queued = false;
    if (!box.offsetWidth) return;                 /* hidden on narrow screens */
    var active = null;
    for (var i = 0; i < items.length; i++) {
      if (items[i].el.getBoundingClientRect().top > 120) break;   /* under the top bar */
      active = items[i];
    }
    var doc = document.documentElement;
    if (window.innerHeight + window.pageYOffset >= doc.scrollHeight - 2) {
      active = items[items.length - 1];           /* the last sections never reach the line */
    }
    if (active === current) return;
    if (current) current.a.removeAttribute('aria-current');
    current = active;
    if (!current) return;
    current.a.setAttribute('aria-current', 'location');
    var r = current.a.getBoundingClientRect(), b = box.getBoundingClientRect();
    if (r.top < b.top + 32) box.scrollTop -= b.top + 32 - r.top;
    else if (r.bottom > b.bottom - 32) box.scrollTop += r.bottom - b.bottom + 32;
  }
  function queue() { if (!queued) { queued = true; window.requestAnimationFrame(update); } }
  window.addEventListener('scroll', queue, { passive: true });
  window.addEventListener('resize', queue);
  update();
})();
