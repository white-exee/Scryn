from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web"])

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>scryn</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#050706; --txt:#86c29b; --hi:#e4ffee; --green:#39f08a;
    --dim:#2f7350; --faint:#1b3d2a; --red:#ff5d5d; --amb:#e0a53a;
    --mono:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box;}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--txt);font-family:var(--mono);font-size:13px;line-height:1.45;}
  body{display:flex;flex-direction:column;height:100vh;overflow:hidden;}
  body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:9;
    background:repeating-linear-gradient(0deg,rgba(0,0,0,0) 0,rgba(0,0,0,0) 2px,rgba(0,0,0,.16) 3px,rgba(0,0,0,0) 4px);}
  ::selection{background:#174a30;color:var(--hi);}
  a{color:var(--green);text-decoration:none;} a:hover{text-decoration:underline;}

  header{padding:14px 16px 8px;border-bottom:1px solid var(--faint);}
  pre.banner{margin:0;color:var(--green);font-size:11px;line-height:1.1;white-space:pre;}
  .sub{color:var(--dim);font-size:11px;margin-top:6px;}
  .sub b{color:var(--txt);}

  #tty{flex:1;overflow-y:auto;padding:14px 16px;white-space:pre-wrap;word-break:break-word;}
  #tty .ln{display:block;}
  .cmd{color:var(--hi);}
  .cmd .p{color:var(--green);}
  .g{color:var(--green);} .hi{color:var(--hi);} .d{color:var(--dim);} .r{color:var(--red);} .a{color:var(--amb);}
  .bar{color:var(--green);} .bar .e{color:var(--faint);}

  form{display:flex;align-items:center;gap:8px;padding:12px 16px;border-top:1px solid var(--faint);background:var(--bg);}
  form .p{color:var(--green);white-space:nowrap;}
  form input{flex:1;background:transparent;border:0;color:var(--hi);font-family:var(--mono);font-size:13px;caret-color:var(--green);}
  form input:focus{outline:none;}
  form input::placeholder{color:var(--faint);}

  #tty::-webkit-scrollbar{width:9px;} #tty::-webkit-scrollbar-thumb{background:#163827;} #tty::-webkit-scrollbar-track{background:transparent;}
  .swatch{cursor:pointer;margin:0 1px;font-size:12px;}
  .swatch:hover{opacity:.7;}
</style>
</head>
<body>
  <header>
<pre class="banner"> ___  ___ _ __ _   _ _ __
/ __|/ __| '__| | | | '_ \\
\\__ \\ (__| |  | |_| | | | |
|___/\\___|_|   \\__, |_| |_|
               |___/</pre>
    <div class="sub"><b>scryn</b> v0.1 &middot; by <a href="https://github.com/white-exee" target="_blank" rel="noopener">white</a> &middot; <span id="srccount">80</span> sources &middot; theme <span id="sw"></span></div>
  </header>

  <div id="tty"></div>

  <form id="f" autocomplete="off">
    <span class="p">scryn&nbsp;&#10095;</span>
    <input id="in" placeholder="target  (username | email | phone | domain …)" autofocus spellcheck="false">
  </form>

<script>
const tty=document.getElementById("tty");
const inp=document.getElementById("in");

function line(html,cls){const d=document.createElement("span");d.className="ln "+(cls||"");d.innerHTML=html;tty.appendChild(d);tty.scrollTop=tty.scrollHeight;return d;}
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function boot(){
  line('<span class="d">type a target and press enter. it is auto-classified.</span>');
  line('<span class="d">examples:</span>');
  line('<span class="d">  </span>torvalds');
  line('<span class="d">  </span>john@example.com  +33612345678  example.com');
  line('&nbsp;');
}

function classify(tok){
  if(/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(tok))return["email",tok];
  if(/^\\+?[0-9][0-9\\s().-]{6,}$/.test(tok))return["phone",tok];
  if(/^[a-z0-9-]+(\\.[a-z0-9-]+)+$/i.test(tok))return["domain",tok];
  return["username",tok];
}

function bar(score){
  const n=Math.round(score/5),full="\\u2588".repeat(n),empty="\\u2588".repeat(20-n);
  return '<span class="bar">'+full+'<span class="e">'+empty+'</span></span>';
}

function map(d){
  const m=d.modules,rows=[];
  if(m.username)rows.push(["username",m.username.found_count+" profiles"]);
  if(m.email)rows.push(["email",esc(m.email.query)+"  mx="+(m.email.deliverable_domain?"yes":"no")]);
  if(m.phone)rows.push(["phone",esc(m.phone.e164||m.phone.query)+"  "+esc(m.phone.region||"")]);
  if(m.domain){let ex=((m.domain.dns.NS||[]).length)+" ns";if((m.domain.subdomains||[]).length)ex+=", "+m.domain.subdomains.length+" subdomains";rows.push(["domain",esc(m.domain.query)+"  "+ex]);}
  line('<span class="hi">'+esc(d.target)+'</span>');
  rows.forEach((r,i)=>{const br=i===rows.length-1?"\\u2514\\u2500 ":"\\u251c\\u2500 ";line('<span class="d">'+br+'</span>'+r[0]+' <span class="d">'+r[1]+'</span>');});
}

async function run(raw){
  line('<span class="cmd"><span class="p">scryn \\u276f</span> '+esc(raw)+'</span>');
  const body={};
  raw.split(/\\s+/).filter(Boolean).forEach(t=>{const [k,v]=classify(t);body[k]=v;});
  if(!Object.keys(body).length){line('<span class="r">[!] empty target</span>');return;}
  line('<span class="d">[*] target: </span>'+Object.entries(body).map(([k,v])=>k+"="+esc(v)).join("  "));
  line('<span class="d">[*] querying sources…</span>');
  let d;
  try{const r=await fetch("/api/scan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});d=await r.json();}
  catch(err){line('<span class="r">[!] request failed: '+esc(err)+'</span>');return;}
  if(d.error){line('<span class="r">[!] '+esc(d.error)+'</span>');return;}
  const m=d.modules;

  if(m.username){
    const f=m.username.results.filter(r=>r.status==="found");
    line('<span class="d">── username ── </span>'+esc(m.username.query)+' <span class="d">('+m.username.found_count+"/"+m.username.checked+')</span>');
    if(f.length)f.forEach(r=>line('  <span class="g">[+]</span> '+r.platform.padEnd(13).replace(/ /g,"&nbsp;")+'<a href="'+r.url+'" target="_blank" rel="noopener">'+esc(r.url)+'</a>'));
    else line('  <span class="d">[-] no profiles matched</span>');
  }
  if(m.email){const e=m.email;
    line('<span class="d">── email ── </span>'+esc(e.query));
    line('  valid='+flag(e.valid_format)+'  mx='+flag(e.deliverable_domain)+'  gravatar='+flag(e.gravatar));
    if(e.mx_records.length)line('  <span class="d">mx:</span> '+esc(e.mx_records.join(", ")));
    if(e.gravatar_profile){const gp=e.gravatar_profile;
      line('  <span class="d">gravatar:</span> <span class="hi">'+esc(gp.display_name||"?")+'</span>'+(gp.location?' <span class="d">'+esc(gp.location)+'</span>':''));
      gp.accounts.slice(0,8).forEach(a=>line('    <span class="g">\\u21b3</span> '+esc(a.service||"?").padEnd(12).replace(/ /g,"&nbsp;")+'<a href="'+a.url+'" target="_blank" rel="noopener" class="d">'+esc(a.url)+'</a>'));
    }
  }
  if(m.phone){const p=m.phone;
    line('<span class="d">── phone ── </span>'+esc(p.query));
    line('  valid='+flag(p.valid)+'  region=<span class="hi">'+esc(p.region||"—")+'</span>  carrier=<span class="hi">'+esc(p.carrier||"—")+'</span>  type='+esc(p.line_type||"—"));
  }
  if(m.domain){const dm=m.domain;
    line('<span class="d">── domain ── </span>'+esc(dm.query));
    line('  <span class="d">registrar</span> '+esc(dm.whois.registrar||"—"));
    Object.entries(dm.dns).filter(([t,v])=>v.length).forEach(([t,v])=>{
      if(t==="TXT"&&v.length>3)line('  <span class="d">txt&nbsp;&nbsp;</span> '+v.length+' records <span class="d">(use the api for full)</span>');
      else line('  <span class="d">'+t.toLowerCase().padEnd(5).replace(/ /g,"&nbsp;")+'</span> '+esc(v.join(", ")));
    });
    const es=dm.email_security||{};
    line('  <span class="d">spf&nbsp;&nbsp;</span> '+flag(es.spf)+' <span class="d">'+esc(es.spf_policy||"")+'</span>&nbsp;&nbsp; <span class="d">dmarc</span> '+flag(es.dmarc)+' <span class="d">'+esc(es.dmarc_policy||"")+'</span>');
    const subs=dm.subdomains||[];
    if(subs.length){
      line('  <span class="d">subs&nbsp;</span> '+subs.length+' subdomains <span class="d">(crt.sh)</span>');
      subs.slice(0,8).forEach(s=>line('    <span class="g">\\u00b7</span> '+esc(s)));
      if(subs.length>8)line('    <span class="d">\\u2026 +'+(subs.length-8)+' more (api for full)</span>');
    }
  }

  line('&nbsp;');
  line('<span class="d">── map ──</span>');
  map(d);
  line('&nbsp;');
  const bdown=Object.entries(d.score_breakdown).map(([k,v])=>k+" +"+v).join("  ");
  line('<span class="hi">confidence '+d.score+'/100</span>  '+bar(d.score));
  if(bdown)line('<span class="d">'+bdown+'</span>');
  line('&nbsp;');
}

function flag(b){return b?'<span class="g">yes</span>':'<span class="d">no</span>';}

document.getElementById("f").addEventListener("submit",async(e)=>{
  e.preventDefault();
  const raw=inp.value.trim();if(!raw)return;
  inp.value="";inp.disabled=true;
  await run(raw);
  inp.disabled=false;inp.focus();
});

const THEMES={green:"#39f08a",amber:"#f0c04f",red:"#ff5d5d",cyan:"#51e0e0",magenta:"#e86af0",blue:"#5aa0ff",white:"#e4ffee"};
function setAccent(col){try{document.documentElement.style.setProperty("--green",col);localStorage.setItem("scryn-accent",col);}catch(e){document.documentElement.style.setProperty("--green",col);}}
const sw=document.getElementById("sw");
Object.entries(THEMES).forEach(([name,col])=>{const b=document.createElement("span");b.className="swatch";b.style.color=col;b.textContent="\\u2588";b.title=name;b.onclick=()=>setAccent(col);sw.appendChild(b);});
try{const saved=localStorage.getItem("scryn-accent");if(saved)document.documentElement.style.setProperty("--green",saved);}catch(e){}

boot();
document.addEventListener("click",(ev)=>{if(ev.target.closest("#sw"))return;if(!window.getSelection().toString())inp.focus();});
</script>
</body>
</html>"""


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return _PAGE
