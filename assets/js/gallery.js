/* Renders the gallery from PHOTOS (assets/js/photos.js) and runs the lightbox. */
(function () {
  var grid = document.getElementById('gallery');
  if (!grid) return;

  var photos = (typeof PHOTOS !== 'undefined' && PHOTOS) || [];

  if (!photos.length) {
    grid.outerHTML =
      '<p class="gallery-empty">No photos yet. Drop files into ' +
      '<code>assets/photos/originals/</code> and run ' +
      '<code>python3 scripts/build-photos.py</code>.</p>';
    return;
  }

  /* ---- grid ---- */

  photos.forEach(function (photo, i) {
    var figure = document.createElement('figure');
    figure.className = 'shot' + (photo.feature ? ' shot--feature' : '');

    var button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-label', 'View ' + photo.title + ' larger');
    button.dataset.index = String(i);

    var img = document.createElement('img');
    img.src = photo.thumb;
    img.alt = photo.title + (photo.place ? ', ' + photo.place : '');
    img.width = photo.w;
    img.height = photo.h;
    img.loading = i < 2 ? 'eager' : 'lazy';
    img.decoding = 'async';

    button.appendChild(img);
    figure.appendChild(button);

    if (photo.title || photo.place || photo.year) {
      var caption = document.createElement('figcaption');
      if (photo.title) {
        var b = document.createElement('b');
        b.textContent = photo.title;
        caption.appendChild(b);
      }
      [photo.place, photo.year].forEach(function (text) {
        if (!text) return;
        var span = document.createElement('span');
        span.textContent = text;
        caption.appendChild(span);
      });
      figure.appendChild(caption);
    }

    grid.appendChild(figure);
  });

  /* ---- lightbox ---- */

  var box = document.getElementById('lightbox');
  var boxImg = box.querySelector('img');
  var boxCap = box.querySelector('.lightbox__cap');
  var index = 0;
  var lastFocused = null;

  if (photos.length < 2) {
    box.querySelectorAll('.lightbox__nav').forEach(function (nav) {
      nav.hidden = true;
    });
  }

  function show(i) {
    index = (i + photos.length) % photos.length;
    var photo = photos[index];
    boxImg.src = photo.src;
    boxImg.alt = photo.title + (photo.place ? ', ' + photo.place : '');
    boxCap.textContent = [photo.title, photo.place, photo.year]
      .filter(Boolean).join(' · ');
  }

  function open(i) {
    lastFocused = document.activeElement;
    show(i);
    box.classList.add('is-open');
    box.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    box.querySelector('.lightbox__close').focus();
  }

  function close() {
    box.classList.remove('is-open');
    box.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (lastFocused) lastFocused.focus();
  }

  grid.addEventListener('click', function (event) {
    var button = event.target.closest('button[data-index]');
    if (button) open(Number(button.dataset.index));
  });

  box.addEventListener('click', function (event) {
    if (event.target === box || event.target === boxImg.parentNode) close();
  });

  box.querySelector('.lightbox__close').addEventListener('click', close);
  box.querySelector('.lightbox__nav--prev').addEventListener('click', function () {
    show(index - 1);
  });
  box.querySelector('.lightbox__nav--next').addEventListener('click', function () {
    show(index + 1);
  });

  document.addEventListener('keydown', function (event) {
    if (!box.classList.contains('is-open')) return;
    if (event.key === 'Escape') close();
    if (event.key === 'ArrowLeft') show(index - 1);
    if (event.key === 'ArrowRight') show(index + 1);
  });
})();
