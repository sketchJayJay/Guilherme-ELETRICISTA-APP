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
  const s=document.querySelector('.sidebar');
  if(!s)return;
  if(s.classList.contains('open')&&!s.contains(e.target)&&!e.target.closest('.menu-btn')) closeSidebar();
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
