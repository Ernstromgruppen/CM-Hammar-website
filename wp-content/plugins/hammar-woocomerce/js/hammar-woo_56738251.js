
jQuery(document).ready(function () {
  (function ($) {


    /* ---------------------------------------------- /*
     * Scroll States
    /* ---------------------------------------------- */
    function ScrollStates() {

      var self = this,
        win = $(document.body),
        $nav = $('body header:not("body.home header")'),
        currentScroll,
        lastScroll;

      self.init = function () {
        win.bind('scroll', self.windowScroll);
        self.windowScroll();
      }

      self.windowScroll = function () {

        currentScroll = win.scrollTop();

        if (currentScroll > 60) {
          $nav.addClass('navbar-sticky');
        } else {
          $nav.removeClass('navbar-sticky');
        }

        lastScroll = currentScroll;
      }
    }

    // Run
    var scrollstates = new ScrollStates();
    scrollstates.init();

  })(jQuery)

});