/* Renders the gallery from PHOTOS (assets/js/photos.js) and runs the lightbox. */
(function () {
  var grid = document.getElementById('gallery');
  if (!grid) return;

  var photos = (typeof PHOTOS !== 'undefined' && PHOTOS) || [];

  /* Most photos carry no caption, so fall back to the section name for alt text
     rather than leaving a screen reader with nothing. */
  function describe(photo) {
    return [photo.title, photo.place || photo.group].filter(Boolean).join(', ');
  }

  if (!photos.length) {
    grid.outerHTML =
      '<p class="gallery-empty">No photos yet. Drop files into ' +
      '<code>assets/photos/originals/</code> and run ' +
      '<code>python3 scripts/build-photos.py</code>.</p>';
    return;
  }

  /* ---- grid ----
     Photos are grouped by year. Once there is more than one year, each gets its
     own heading and its own column block, so a long gallery stays navigable
     instead of running as one endless wall. */

  var groups = [];
  photos.forEach(function (p) {
    var g = p.group || '';
    if (groups.indexOf(g) === -1) groups.push(g);
  });
  var grouped = groups.length > 1;
  var container = grid.parentNode;
  var currentGroup = null;
  var target = grid;

  photos.forEach(function (photo, i) {
    if (grouped && photo.group !== currentGroup) {
      currentGroup = photo.group;
      var heading = document.createElement('h2');
      heading.className = 'gallery-group';
      heading.textContent = currentGroup;
      if (target === grid && !target.childNodes.length) {
        container.insertBefore(heading, grid);
      } else {
        container.appendChild(heading);
        target = document.createElement('div');
        target.className = 'gallery';
        container.appendChild(target);
      }
    }
    var figure = document.createElement('figure');
    figure.className = 'shot' + (photo.feature ? ' shot--feature' : '');

    var button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-label', 'View ' + photo.title + ' larger');
    button.dataset.index = String(i);

    var img = document.createElement('img');
    img.src = photo.thumb;
    img.alt = describe(photo);
    img.width = photo.w;
    img.height = photo.h;
    img.loading = i < 2 ? 'eager' : 'lazy';
    img.decoding = 'async';

    if (photo.thumbWebp) {
      var picture = document.createElement('picture');
      var source = document.createElement('source');
      source.type = 'image/webp';
      source.srcset = photo.thumbWebp;
      picture.appendChild(source);
      picture.appendChild(img);
      button.appendChild(picture);
    } else {
      button.appendChild(img);
    }
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

    target.appendChild(figure);
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

  var boxSource = box.querySelector('source');

  function show(i) {
    index = (i + photos.length) % photos.length;
    var photo = photos[index];
    if (boxSource) boxSource.srcset = photo.srcWebp || photo.src;
    boxImg.src = photo.src;
    boxImg.alt = describe(photo);
    boxCap.textContent = [photo.title, photo.place || photo.group, photo.year]
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

  container.addEventListener('click', function (event) {
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
