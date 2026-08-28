function toggleSidebar(){
  const s=document.querySelector('.sidebar');
  if(!s)return;
  const open=!s.classList.contains('open');
  s.classList.toggle('open',open);
  document.body.classList.toggle('sidebar-open',open);
}
function closeSidebar(){
  document.querySelector('.sidebar')?.classList.remove('open');
  document.body.classList.remove('sidebar-open');
}
document.addEventListener('click',e=>{
  const sidebar=document.querySelector('.sidebar');
  if(!sidebar)return;
  // Não feche o menu no mesmo toque que acabou de abri-lo.
  // O layout premium usa .menu-square no topo e .mobile-more na barra inferior.
  if(e.target.closest('.menu-square, .mobile-more')) return;
  if(sidebar.classList.contains('open') && !sidebar.contains(e.target)) closeSidebar();
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeSidebar()});
function confirmDelete(msg='Tem certeza que deseja excluir?'){return window.confirm(msg)}
function moneyBR(v){return Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}
function formatDuration(sec){sec=Math.max(0,parseInt(sec||0));const h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),s=sec%60;return h?`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`:`${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`}

// Give each table cell its column name so CSS can turn desktop tables into readable mobile cards.
function prepareResponsiveTables(){
  document.querySelectorAll('table.table').forEach(table=>{
    const headers=[...table.querySelectorAll('thead th')].map(th=>th.textContent.trim());
    table.querySelectorAll('tbody tr').forEach(row=>{
      [...row.children].forEach((cell,i)=>{
        if(cell.hasAttribute('colspan')) return;
        cell.dataset.label=headers[i]||'';
      });
    });
  });
}

// Keep the currently focused field visible above the fixed mobile navigation and keyboard.
function improveMobileForms(){
  if(!window.matchMedia('(max-width: 760px)').matches)return;
  document.querySelectorAll('input,select,textarea').forEach(el=>{
    el.addEventListener('focus',()=>setTimeout(()=>el.scrollIntoView({block:'center',behavior:'smooth'}),250));
  });
}

document.addEventListener('DOMContentLoaded',()=>{
  prepareResponsiveTables();
  improveMobileForms();
});

// Searchable client picker used anywhere a client must be selected.
function initClientPickers(){
  document.querySelectorAll('[data-client-picker]').forEach(picker=>{
    const input=picker.querySelector('[data-client-search]');
    const select=picker.querySelector('[data-client-select]');
    const results=picker.querySelector('[data-client-results]');
    if(!input||!select||!results)return;
    const items=[...select.options].filter(o=>o.value).map(o=>({
      value:o.value,
      name:o.dataset.name||o.textContent.trim(),
      phone:o.dataset.phone||'',
      phoneDigits:(o.dataset.phone||'').replace(/\D/g,''),
      label:o.textContent.trim()
    }));
    const selected=select.options[select.selectedIndex];
    if(selected&&selected.value){input.value=selected.dataset.name||selected.textContent.trim();input.dataset.selectedValue=selected.value;}

    const close=()=>{results.innerHTML='';results.classList.remove('open')};
    const choose=item=>{
      select.value=item.value;
      input.value=item.name;
      input.dataset.selectedValue=item.value;
      close();
      select.dispatchEvent(new Event('change',{bubbles:true}));
    };
    const render=()=>{
      const q=(input.value||'').trim().toLowerCase();
      const qDigits=q.replace(/\D/g,'');
      if(input.dataset.selectedValue&&select.value===input.dataset.selectedValue){
        const current=items.find(x=>x.value===select.value);
        if(current&&current.name.toLowerCase()===q){close();return;}
      }
      select.value='';
      input.dataset.selectedValue='';
      const filtered=items.filter(x=>!q||x.name.toLowerCase().includes(q)||x.phone.toLowerCase().includes(q)||(qDigits&&x.phoneDigits.includes(qDigits))).slice(0,8);
      results.innerHTML='';
      if(!filtered.length){
        const empty=document.createElement('div');empty.className='client-result-empty';empty.textContent='Nenhum cliente encontrado';results.appendChild(empty);
      }else{
        filtered.forEach(item=>{
          const b=document.createElement('button');
          b.type='button';b.className='client-result';
          b.innerHTML=`<strong>${escapeHtml(item.name)}</strong>${item.phone?`<span>${escapeHtml(item.phone)}</span>`:''}`;
          b.addEventListener('click',()=>choose(item));
          results.appendChild(b);
        });
      }
      results.classList.add('open');
    };
    input.addEventListener('focus',render);
    input.addEventListener('input',render);
    input.addEventListener('blur',()=>setTimeout(()=>{
      if(select.value)return;
      const q=(input.value||'').trim().toLowerCase();
      const qDigits=q.replace(/\D/g,'');
      if(!q)return;
      const filtered=items.filter(x=>x.name.toLowerCase().includes(q)||x.phone.toLowerCase().includes(q)||(qDigits&&x.phoneDigits.includes(qDigits)));
      if(filtered.length===1)choose(filtered[0]);
    },120));
    input.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
    document.addEventListener('click',e=>{if(!picker.contains(e.target))close()});
  });
}
function escapeHtml(v){
  return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

document.addEventListener('DOMContentLoaded',initClientPickers);
