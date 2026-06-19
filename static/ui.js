// ui.js -- small UI helpers: autosize textareas, toasts, copy, fill, and submit spinner
document.addEventListener('DOMContentLoaded', () => {
  // Autosize textareas
  function autosize(el){
    if(!el) return;
    el.style.height = 'auto';
    el.style.height = (el.scrollHeight) + 'px';
  }

  const mainText = document.getElementById('main_text');
  const summText = document.getElementById('summ_text');
  [mainText, summText].forEach(el => {
    if(!el) return;
    autosize(el);
    el.addEventListener('input', () => autosize(el));
  });

  // Toast
  const toastContainer = document.getElementById('toast-container');
  function toast(message, duration=2000){
    if(!toastContainer) return;
    const t = document.createElement('div');
    t.className = 'toast';
    t.textContent = message;
    toastContainer.appendChild(t);
    requestAnimationFrame(()=> t.classList.add('visible'));
    setTimeout(()=>{ t.classList.remove('visible'); setTimeout(()=> t.remove(),300); }, duration);
  }

  // Copy helper
  window.copyText = function(id){
    const el = document.getElementById(id);
    if(!el) { toast('No source text'); return; }
    const text = el.innerText || el.textContent || '';
    navigator.clipboard.writeText(text).then(()=> toast('Copied to clipboard')).catch(()=> toast('Copy failed'));
  }

  // Fill helpers
  window.fillFrom = function(id){
    const el = document.getElementById(id);
    const target = document.getElementById('main_text');
    if(!el || !target) { toast('No source text found'); return; }
    target.value = el.innerText || el.textContent || '';
    autosize(target);
    toast('Filled translation input');
  }
  window.fillSummFrom = function(id){
    const el = document.getElementById(id);
    const target = document.getElementById('summ_text');
    if(!el || !target) { toast('No source text found'); return; }
    target.value = el.innerText || el.textContent || '';
    autosize(target);
    toast('Filled summary input');
  }

  // Keep hidden inputs in sync (download forms)
  function syncHidden(){
    const ocr = document.getElementById('ocr_text');
    const pdf = document.getElementById('pdf_text');
    const trans = document.getElementById('translated');
    const sum = document.getElementById('summary');
    if(ocr){ const inp = document.getElementById('ocr_text_input'); if(inp) inp.value = ocr.innerText; }
    if(pdf){ const inp2 = document.getElementById('pdf_text_input'); if(inp2) inp2.value = pdf.innerText; }
    if(trans){ const tin = document.getElementById('translated_input'); if(tin) tin.value = trans.innerText; }
    if(sum){ const sin = document.getElementById('summary_input'); if(sin) sin.value = sum.innerText; }
  }
  syncHidden();

  // Spinner on translate submit
  const translateForm = document.getElementById('translateForm');
  if(translateForm){
    translateForm.addEventListener('submit', ()=>{
      const btn = translateForm.querySelector('button[type=submit]');
      if(btn){ btn.classList.add('loading'); btn.disabled = true; }
    });
  }
  // Spinner on summarize submit
  const summForm = document.getElementById('summForm');
  if(summForm){
    summForm.addEventListener('submit', ()=>{
      const btn = summForm.querySelector('button[type=submit]');
      if(btn){ btn.classList.add('loading'); btn.disabled = true; }
    });
  }
});

// small helper to show toast programmatically
window.showToast = function(msg){
  const ev = new Event('DOMContentLoaded');
  document.dispatchEvent(ev);
  // if toast available
  const tc = document.getElementById('toast-container');
  if(tc){ const d = document.createElement('div'); d.className='toast visible'; d.textContent = msg; tc.appendChild(d); setTimeout(()=> d.remove(),2000); }
}
