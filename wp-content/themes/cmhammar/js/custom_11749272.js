(function ($) {

	/* ---------------------------------------------- /*
	 * Close/Open Main Menu
	/* ---------------------------------------------- */
	$(window).on("load", function () {
		$(".ham, .open-main-menu .logo, .main-menu ul a:first-child").on("click", function () {
			$("body").toggleClass("open-main-menu");
		});
	});

	/* ---------------------------------------------- /*
	 * Page scroller
	/* ---------------------------------------------- */
	// Check if section exists
	var section = $('section[class="section"]');
	var total = section.length;

	for (var i = 0; i < section.length; i++) {

		// Store ID
		var sectionID = '#section' + i;

		if ($(sectionID).length) {

			// Get next sections ID
			var nextSectionID = '#section' + (i + 1);

			// Get next sections anchor name
			var anchorName = '#' + $(nextSectionID).attr('data-anchor');

			// Set current sections anchor link
			$(sectionID).find('.page-scroller').attr('href', anchorName);
		}

		// Last section
		if (i === total - 1) {
			// Get current sections ID
			var sectionID = '#section' + (i + 1);
			$(sectionID).find('.page-scroller').attr('href', '#footer');
		}
	}

	/* ---------------------------------------------- /*
	 * Dropdown for categories
	/* ---------------------------------------------- */
	$(".cat-menu > ul > li > .js-menu-accordion").click(function (event) {
		$(this).find('.rotate').toggleClass("down");
		$(this).parent().toggleClass("show-sub-menu");
		event.preventDefault();
	});


	/* ---------------------------------------------- /*
	 * Scroll States
	/* ---------------------------------------------- */
	function ScrollStates() {

		var self = this,
			win = $(window),
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


	/* ---------------------------------------------- /*
	 * Language Switcher for Polylang
	/* ---------------------------------------------- */
	// Change order, current lang first
	$('.lang-switcher li.current-lang').insertBefore('.lang-switcher li:eq(0)');

	// Show/hide submenu
	$(".lang-switcher > ul > li > a").click(function (event) {
		$(this).parent().children().toggleClass("show");
		event.preventDefault();
	});





})(jQuery)


