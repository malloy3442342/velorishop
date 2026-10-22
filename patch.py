from pathlib import Path
p = Path("index.html")
s = p.read_text(encoding="utf-8")
a = s.index('$("f").onsubmit=e=>{')
end = '$("ot").value=msg;\n};'
b = s.index(end, a) + len(end)
new = r'''$("f").onsubmit=async e=>{
 e.preventDefault(); if(!cart.length)return;
 const fb=$("fb"), btn=$("go");
 const phone=normPhone($("ph").value);
 const say=(m,ok)=>{fb.innerHTML="";const p=document.createElement("p");p.style.cssText="margin:6px 0;font-size:14px;color:"+(ok?"var(--ink)":"#d92d20");p.textContent=m;fb.appendChild(p)};
 if(!phone)return say("Введите номер полностью, например +998 90 123 45 67");
 const body={name:$("nm").value.trim(),phone,items:cart.map(x=>({id:x.id,z:x.z,q:x.q})),account:user?`${user.name} (${user.id})`:"",init_data:(tg&&tg.initData)||""};
 btn.disabled=true; btn.textContent="Отправляем…"; say("");
 try{
  const r=await fetch("/api/order",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const j=await r.json().catch(()=>({}));
  if(r.ok&&j.ok){cart=[];render();say(`Заказ №${j.id} принят! Мы свяжемся с вами в Telegram.`,true)}
  else say(j.error||"Не удалось отправить заказ. Попробуйте ещё раз.");
 }catch(x){say("Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.")}
 finally{btn.textContent="Оформить заказ";btn.disabled=!cart.length}
};'''
s = s[:a] + new + s[b:]
s = s.replace(">Оформить в Telegram<", ">Оформить заказ<")
p.write_text(s, encoding="utf-8")
print("Готово")
