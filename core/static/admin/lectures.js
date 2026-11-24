(function(){"use strict";
 document.querySelectorAll('form[data-confirm]').forEach(form=>form.addEventListener('submit',e=>{if(!confirm(form.dataset.confirm))e.preventDefault()}));
 document.querySelectorAll('.lm-form').forEach(form=>{let sending=false;form.addEventListener('submit',e=>{if(sending){e.preventDefault();return}sending=true;const status=document.createElement('p');status.setAttribute('role','status');status.textContent='Saqlanmoqda… Iltimos, sahifani yopmang.';form.append(status);form.querySelectorAll('button[type=submit],.sd-submit button').forEach(button=>button.setAttribute('aria-disabled','true'))})});
 const form=document.getElementById('page-actions');if(!form)return;
 const boxes=[...form.querySelectorAll('input[name=pages]')],all=form.querySelector('[data-select-all]');
 function count(){const n=boxes.filter(b=>b.checked).length;form.querySelector('[data-selected]').textContent=n+' ta tanlangan';all.checked=!!boxes.length&&n===boxes.length;all.indeterminate=n>0&&n<boxes.length}
 all.addEventListener('change',()=>{boxes.forEach(b=>b.checked=all.checked);count()});boxes.forEach(b=>b.addEventListener('change',count));
 form.addEventListener('submit',e=>{if(!boxes.some(b=>b.checked)){e.preventDefault();alert('Avval kerakli sahifalarni belgilang.');return}if(e.submitter?.dataset.confirm&&!confirm(e.submitter.dataset.confirm))e.preventDefault()});
 form.querySelectorAll('[data-move]').forEach(button=>button.addEventListener('click',()=>{const post=document.createElement('form');post.method='post';post.action=button.dataset.url;for(const [name,value] of [['csrfmiddlewaretoken',form.querySelector('[name=csrfmiddlewaretoken]').value],['pages',button.dataset.move]]){const input=document.createElement('input');input.type='hidden';input.name=name;input.value=value;post.append(input)}document.body.append(post);post.submit()}));
})();
