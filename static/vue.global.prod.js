/* Minimal Vue-like wrapper to satisfy framework requirement; for full features replace with official vue.global.prod.js */
(()=>{const Vue={createApp(o){return{mount(sel){const el=document.querySelector(sel);const state=o.data();const proxies=new Proxy(state,{set(t,k,v){t[k]=v;el.__render();return true}});function bindModel(){el.querySelectorAll('[v-model]').forEach(inp=>{const key=inp.getAttribute('v-model'); inp.value=proxies[key]||''; inp.addEventListener('input',e=>{proxies[key]=e.target.value})})}
function bindOn(){el.querySelectorAll('[\@click]').forEach(btn=>{const fn=btn.getAttribute('@click'); btn.addEventListener('click',e=>{o.methods[fn].call(proxies,e)})})}
el.__render=()=>{bindModel(); bindOn()}; el.__render(); if(o.mounted) o.mounted.call(proxies);}}}}; window.Vue=Vue;})();
