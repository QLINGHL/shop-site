
(function(){
var K='shop-theme';
function sysD(){return window.matchMedia&&matchMedia('(prefers-color-scheme:dark)').matches}
function mode(){try{return localStorage.getItem(K)||'auto'}catch(e){return'auto'}}
function apply(){var m=mode();var d=m==='dark'||(m==='auto'&&sysD());document.documentElement.classList.toggle('dark',d);var b=document.querySelectorAll('#setThemes [data-theme]');for(var i=0;i<b.length;i++)b[i].classList.toggle('is-on',b[i].getAttribute('data-theme')===m)}
function init(){apply();var b=document.querySelectorAll('#setThemes [data-theme]');for(var i=0;i<b.length;i++)(function(x){x.addEventListener('click',function(){try{localStorage.setItem(K,x.getAttribute('data-theme'))}catch(e){}apply()})})(b[i]);var mq=window.matchMedia&&matchMedia('(prefers-color-scheme:dark)');if(mq){var f=function(){if(mode()==='auto')apply()};if(mq.addEventListener)mq.addEventListener('change',f);else if(mq.addListener)mq.addListener(f)}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
