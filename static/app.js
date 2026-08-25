function toggleSidebar(){document.querySelector('.sidebar')?.classList.toggle('open')}
document.addEventListener('click',e=>{const s=document.querySelector('.sidebar');if(!s)return;if(s.classList.contains('open')&&!s.contains(e.target)&&!e.target.closest('.menu-btn'))s.classList.remove('open')})
function confirmDelete(msg='Tem certeza que deseja excluir?'){return window.confirm(msg)}
function moneyBR(v){return Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}
function formatDuration(sec){sec=Math.max(0,parseInt(sec||0));const h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),s=sec%60;return h?`${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`:`${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`}
