(() => {
  document.querySelectorAll('[data-picture-input]').forEach(input => {
    let temporary;
    const original = input.closest('.wa-picture').querySelector('[data-image-preview]').getAttribute('src');
    input.addEventListener('change', () => {
      const preview = input.closest('.wa-picture').querySelector('[data-image-preview]');
      if (temporary) URL.revokeObjectURL(temporary);
      if (!input.files[0]) {
        preview.hidden = !original;
        if (original) preview.src = original;
        return;
      }
      temporary = URL.createObjectURL(input.files[0]);
      preview.src = temporary;
      preview.hidden = false;
      const clear = input.closest('.wa-picture').querySelector('input[type=checkbox]');
      if (clear) clear.checked = false;
    });
  });
  document.querySelectorAll('.wa-form').forEach(form => {
    form.addEventListener('submit', () => {
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      button.setAttribute('aria-busy', 'true');
    });
  });
  window.addEventListener('pageshow', () => document.querySelectorAll('.wa-form button[type="submit"]').forEach(button => {
    button.disabled = false;
    button.removeAttribute('aria-busy');
  }));
  const error = document.querySelector('.wa-form .has-error input, .wa-form .has-error textarea, .wa-form .has-error select');
  if (error) error.focus();
})();
