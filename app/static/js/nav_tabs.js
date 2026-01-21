(function(){
  // Marcar pestaña activa por path
  var path = location.pathname.replace(/\/+$/, '') || '/';
  var tabs = document.querySelectorAll('.ps-tabs a');
  var active = null;
  tabs.forEach(function(a){
    var ap = a.getAttribute('data-path') || a.getAttribute('href');
    if (ap === path){ a.classList.add('active'); active = a; }
  });

  // Indicador deslizante (solo desktop)
  function placeIndicator(){
    var ind = document.querySelector('.ps-tabs-indicator');
    if (!ind || !active) return;
    var rectTabs = ind.parentElement.getBoundingClientRect();
    var rectA    = active.getBoundingClientRect();
    var left = rectA.left - rectTabs.left;
    ind.style.width = rectA.width + 'px';
    ind.style.transform = 'translateX(' + left + 'px)';
  }
  placeIndicator();
  window.addEventListener('resize', placeIndicator);

  // Propagar ?user_id en todos los enlaces internos
  var uid = new URLSearchParams(location.search).get('user_id');
  if (uid){
    document.querySelectorAll('a[href^="/"]').forEach(function(a){
      try{
        var url = new URL(a.getAttribute('href'), location.origin);
        if (!url.searchParams.get('user_id')){
          url.searchParams.set('user_id', uid);
          a.setAttribute('href', url.pathname + '?' + url.searchParams.toString());
        }
      }catch(e){}
    });
  }
})();
