$(document).ready(function () {
    var socket = io.connect(window.location.protocol + '//' + document.domain + ':' + location.port);

    let abstractRelatedReviews = '';

    function setPubDate() {
        var pub_year = ($('#pub_date').html());
        pub_date = new Date(pub_year, 1, 1);
        var days = (Math.round((new Date() - pub_date) / (1000 * 60 * 60 * 24))).toFixed(0);
        if (days >= 365) {
            var years = (days / 365).toFixed(2);
            $('#time_since_pub').html(years + ' years');
        } else {
            $('#time_since_pub').html(days + ' days');
        }
    }

    function debounce(func, wait, immediate) {
        var timeout;

        return function executedFunction() {
            var context = this;
            var args = arguments;

            var later = function () {
                timeout = null;
                if (!immediate) func.apply(context, args);
            };

            var callNow = immediate && !timeout;

            clearTimeout(timeout);

            timeout = setTimeout(later, wait);

            if (callNow) func.apply(context, args);
        };
    }

    function numberWithCommas(x) {
        return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    }

    function gen_plot(msg) {
        var data = msg['data'];
        var plt = Bokeh.Plotting;
        var yy = data['y'];
        var xx = data['x'];
        var colours = data['colours'];
        var ydr = new Bokeh.Range1d({start: -70.038440855407714, end: 70.644477995300306});
        var xdr = new Bokeh.Range1d({start: -69.551894338989271, end: 64.381507070922851});
        var source = new Bokeh.ColumnDataSource({
            data: {
                x: xx,
                y: yy
            }
        });
        var image = new Bokeh.ImageURL({
            url: data['img'],
            x: xdr.start - 2.0, y: ydr.end, w: ydr.end - ydr.start - 2.7,
            h: (xdr.end - xdr.start) + 6.7, anchor: 'top_left'
        });
        var p = plt.figure({
            plot_width: 550,
            plot_height: 550,
            x_range: xdr,
            y_range: ydr
        });
        p.add_glyph(image);
        var circles = p.circle({field: 'x'}, {field: 'y'}, {
            source: source,
            radius: 0.2,
            fill_color: colours,
            line_color: null,
            fill_alpha: 0.8
        });
        p.yaxis[0].visible = false;
        p.xaxis[0].visible = false;
        p.xgrid[0].visible = false;
        p.ygrid[0].visible = false;
        p.border_fill_color = null;
        p.outline_line_color = null;
        return p;
    }

    // function refresh_dashboard() {
    //     var num_i = 0;
    //     var interval = setInterval(function () {
    //         var target = $("#incl_trials_container .panel").length;
    //         $('#num_incl_trials').text(num_i);
    //         if (num_i >= target) clearInterval(interval);
    //         num_i++;
    //     }, 30);
    //     var incl_part = 0;
    //     $(".incl-enrol").each(function () {
    //         if (parseInt($(this).attr('title'))) {
    //             incl_part += parseInt($(this).attr('title'));
    //         }
    //     });
    //     var num_p = 0;
    //     var interval2 = setInterval(function () {
    //         $('#part_incl_trials').text(num_p);
    //         if (num_p >= incl_part) {
    //             clearInterval(interval2);
    //             $('#part_incl_trials').text(incl_part);
    //         }
    //         num_p += parseInt((incl_part / 66).toFixed());
    //     }, 30);
    // }


    // TRIAL PAGES
    // this file is spaghetti
    if (window.location.pathname?.startsWith('/trials/')) {

    }

    //
    // /**
    //  * Set the current published trial articles page
    //  * @param num =  page num
    //  */
    // const setTrialPubPage = num => {
    //     const maxPage = $('#pubpages').children().length;
    //     const $nav = $('#pubpage-nav');
    //
    //     // Extra logic to change visible page numbers if we have more than 5 pages
    //     if (maxPage > 5) {
    //
    //         // This is initially the pagenum of the first of the 5 pager buttons
    //         // Incremented by 1 per iteration as we loop over the buttons and set their new values
    //         let numToSet = Math.min(Math.max(num - 2, 1), maxPage - 4);
    //         $('#pubpage-nav').find('a').each((i, page) => {
    //             const action = $(page).attr('data-page');
    //             if (isNaN(action)) return;
    //             $(page).attr('data-page', numToSet).text(numToSet);
    //             numToSet++;
    //         });
    //
    //     }
    //     $nav.find('a').parent().removeClass('active');
    //     $nav.find(`a[data-page="${num}"]`).parent().addClass('active');
    //
    //     // Set number on the page buttons
    //     // $('#pubpage-link-1').text((num - 1) || 1).parent().removeClass('active');
    //     // $('#pubpage-link-2').text(num).parent().addClass('active');
    //     // $('#pubpage-link-3').text(num + 1).parent().removeClass('active');
    //     //
    //     $('.pubpage').hide();
    //     $(`#pubpage-${num}`).show();
    // };
    //
    //
    // if (['/tp', '/trial'].includes(window.location.pathname) && window.location.href.indexOf('trialid') > -1) {
    //     const trialId = getUrlParameter('trialid');
    //
    //     // NCT trial page
    //     if (trialId.startsWith('NCT')) {
    //         console.log('on trial page');
    //
    //         // More related reviews behaviour
    //         let shownRelatedReviews = 5;
    //         const totalRelatedReviews = $('#related-reviews-list').children('div.panel-default').length;
    //         if (shownRelatedReviews < totalRelatedReviews) {
    //             $('#more_related_reviews').show();
    //         }
    //         $('#related-reviews-list div.panel-default').hide();
    //         $('#related-reviews-list div.panel-default:lt(' + shownRelatedReviews + ')').show();
    //
    //         $('#more_related_reviews').on('click', () => {
    //             shownRelatedReviews = (shownRelatedReviews + 5 <= totalRelatedReviews) ? shownRelatedReviews + 5 : totalRelatedReviews;
    //             $('#related-reviews-list div.panel-default:lt(' + shownRelatedReviews + ')').show();
    //             if (shownRelatedReviews >= totalRelatedReviews) {
    //                 $('#more_related_reviews').hide();
    //             }
    //         });
    //
    //         // More included/linked reviews behaviour
    //         let shownLinkedReviews = 5;
    //         const totalLinkedReviews = $('#linked-reviews-list').children('div.panel-default').length;
    //         if (shownLinkedReviews < totalLinkedReviews) {
    //             $('#more_linked_reviews').show();
    //         }
    //         $('#linked-reviews-list div.panel-default').hide();
    //         $('#linked-reviews-list div.panel-default:lt(' + shownLinkedReviews + ')').show();
    //
    //         $('#more_linked_reviews').on('click', () => {
    //             shownLinkedReviews = (shownLinkedReviews + 5 <= totalLinkedReviews) ? shownLinkedReviews + 5 : totalLinkedReviews;
    //             $('#linked-reviews-list div.panel-default:lt(' + shownLinkedReviews + ')').show();
    //             if (shownLinkedReviews >= totalLinkedReviews) {
    //                 $('#more_linked_reviews').hide();
    //             }
    //         });
    //
    //         // Pagination trial publications
    //         let currentPage = 1;
    //         // Hide if button if its page doesnt exist
    //         $('#pubpage-nav').find('a').each((i, page) => {
    //             const action = $(page).attr('data-page');
    //
    //             if (isNaN(action)) return;
    //
    //             if (!$(`#pubpage-${action}`).length) {
    //                 $(page).hide();
    //             }
    //         }).on('click', e => {
    //             // On click of a page button
    //             e.preventDefault();
    //
    //             const action = $(e.target).attr('data-page');
    //             currentPage = action === 'prev' ? (currentPage - 1) : action === 'next' ? (currentPage + 1) : +action;
    //             const maxPage = $('#pubpages').children().length;
    //             if (currentPage <= 0) currentPage = 1;
    //             if (currentPage >= maxPage) currentPage = maxPage;
    //             setTrialPubPage(currentPage);
    //         });
    //
    //
    //         // Add new pubmed article
    //         $('#add-pubarticle').on('submit', e => {
    //             e.preventDefault();
    //             const $input = $(e.target).find('[name="article_id"]');
    //             const pubId = $input.val();
    //             if (isNaN(pubId)) {
    //                 return $('#pubarticle-alert').html('<strong>Uh oh! </strong>Please enter a valid PubMed ID.')
    //                     .finish()
    //                     .fadeIn({start: () => $input.addClass('danger')})
    //                     .delay(5000)
    //                     .fadeOut({complete: () => $input.removeClass('danger')});
    //             }
    //
    //             //TODO: add to list,
    //             // - check if already in list
    //             // - check if exists on pubmed
    //             // - success or error
    //             $.ajax({
    //
    //             })
    //         });
    //
    //     } else {
    //         // Trial publication landing page
    //         console.log('on trial pub landing page');
    //         socket.on('my_response', msg => {
    //             console.log('websocket connected, requesting data');
    //             socket.emit('get_trial_panels', {trial_id: trialId});
    //         });
    //         socket.on('trial_panels', msg => {
    //             $('#trial_panels').html(msg.html);
    //         });
    //     }
    //
    // }


    socket.on('blank_update', function (msg) {
        console.log('server update:', msg['msg']);
        $('#progress_txt').text(msg['msg']);
        if (msg['msg'].indexOf('complete') > -1) {
            $('.progress_div').slideUp(1000);
        } else {
            $('.progress_div').slideDown(1000);
        }
    });
    socket.on('page_content', function (msg) {
        if (msg['section'] === 'review_data') {
            $('#review-data-container').html(msg['data']);
            $('#related-reviews').html(msg['related_reviews']);
            $('#review-data-container').slideDown(1000);
            $('#related-reviews').slideDown(1000);
            setPubDate();
        }
        if (msg['section'] === 'search_results') {
            $('.pg_content').attr('style', 'display:none;');
            $('.pg_content').html(msg['data']);
            $('.pg_content').slideDown(1000);
            $('.progress_div').slideUp(1000);
        }
        if (msg['section'] === 'plot') {
            var plot = $('#plot'); // The plot dom element
            plot.removeClass('hidden'); // Show plot
            var data = msg['data']; // The plot data


            var plt = Bokeh.Plotting;

            // Axes data
            var xx = data['dates'].map(Date.parse);
            var yy = data['y_vals'];

            // Circles
            var colors = data['colours'].map(c => plt.color(...c));
            var alpha_vals = data['alpha'];
            var radii = data['enrollment'];
            var max_radii = Math.max(...radii);

            // Review publish date
            var pub_date = Date.parse($('#pub_date').html()) || Date.now();

            // Domain and range
            var y_max = Math.max(...yy);
            var x_max = Math.max(...xx, pub_date);
            var x_min = Math.min(...xx, pub_date);
            var ydr = new Bokeh.Range1d({start: 0, end: y_max + max_radii});
            var xdr = new Bokeh.Range1d({
                start: x_min - 0.13 * (x_max - x_min),
                end: x_max + 0.13 * (x_max - x_min)
            });

            // Published Line

            var label = new Bokeh.Label({
                x: pub_date,
                y: (y_max + max_radii) * 8.6 / 10,
                text: 'Systematic Review Published',
                text_align: 'center',
                background_fill_color: 'white'
            });
            var pubdate = new Bokeh.Span({
                location: pub_date,
                dimension: 'height',
                line_color: 'black',
                line_dash: [5, 5]
            });

            // Create plot
            var source = new Bokeh.ColumnDataSource({
                data: {
                    x: xx,
                    y: yy,
                    colors,
                    alpha: alpha_vals,
                    dates: data['dates'],
                    title: data['titles'],
                    enrollment: data['real_enrollment']
                }
            });
            var tools = 'pan,crosshair,wheel_zoom,box_zoom,reset,save';
            var p = plt.figure({
                tools: tools,
                sizing_mode: 'stretch_both',
                y_range: ydr,
                x_range: xdr,
                x_axis_label: 'trial completion date',
                x_axis_type: 'datetime'
            });
            p.yaxis[0].visible = false;
            p.xgrid[0].visible = false;
            p.ygrid[0].visible = false;
            var renderers = [];
            var circles = p.circle({field: 'x'}, {field: 'y'}, {
                source: source,
                radius: radii,
                radius_dimension: 'y',
                fill_color: colors,
                hover_fill_color: colors,
                fill_alpha: alpha_vals,
                hover_fill_alpha: alpha_vals,
                line_color: null,
                hover_line_color: 'black',
                selection_fill_color: colors,
                nonselection_fill_color: colors,
                selection_line_color: null,
                nonselection_line_color: null,
                selection_fill_alpha: alpha_vals,
                nonselection_fill_alpha: alpha_vals
            });
            renderers.push(circles);
            for (i = 0; i < xx.length; i++) {
                p.line({
                    x: [xx[i], xx[i]],
                    y: [0, yy[i] - radii[i]],
                    line_width: 1,
                    line_color: 'black',
                    line_alpha: 0.3
                });
            }
            var tooltip =
                ('<div>Completion date: @dates</div>' +
                    '<div>ID: @title</div>' +
                    '<div>Participants: @enrollment</div>'
                );
            var hover = new Bokeh.HoverTool({
                tooltips: tooltip,
                mode: 'mouse',
                renderers: renderers
            });
            var cb = new Bokeh.CustomJS({
                args: {source: source}, code: '' +
                    'var nct_id = source.data.title[cb_data.source.selected.indices[0]];' +
                    'var to_move =  $("#panel_" + nct_id);\n' +
                    'to_move.parent().prepend(to_move);' +
                    'if(to_move.is(":hidden")) {to_move.show();} ' +
                    '                        $("#panel_" + nct_id + "> .panel-heading").effect("highlight", {}, 3000);'
            });
            var tap = new Bokeh.TapTool({callback: cb});
            p.add_tools(tap);
            p.add_tools(hover);


            if (msg['page'] === 'reviewdetail') {
                p.add_layout(pubdate);
                p.add_layout(label);
            }

            if (window.location.pathname !== '/blank') {
                $('.progress_div').slideUp(1000);
            }

            if (!$.trim(plot.html())) {
                Bokeh.Plotting.show(p, plot);
                plot.slideDown(2000);


            } else {
                plot.animate({'opacity': 0.01}, 1000, function () {
                    plot.empty();
                    Bokeh.Plotting.show(p, plot);
                    plot.animate({'opacity': 1}, 1000);
                });
            }
        }
        if (msg['section'] === 'recommended_trials') {

            var rel_container = $('#rel_trials_container');
            if (rel_container.is(':empty')) {
                rel_container.html(msg['data']);
                rel_container.slideDown(2000);
                $('#incl_trials_container').slideDown(2000);
            } else {
                var node = $.parseHTML(msg['data']);
                var replacement = $(node).filter('#accordion-rel');
                $('#accordion-rel').html(replacement.html());
            }
            var size_li = $('#accordion-rel').children('div.card').length;
            var x = 10;
            $('#accordion-rel div.card').hide();
            $('#accordion-rel div.card:lt(' + x + ')').show();

            $('#load_more_rel').click(function () {
                x = (x + 5 <= size_li) ? x + 5 : size_li;
                $('#accordion-rel div.card:lt(' + x + ')').show();
                if (x === size_li) {
                    $('#load_more_rel').hide();
                }
            });

        }
        if (msg['section'] === 'related_reviews') {
            $('#related-reviews').html(msg['data']);
            $('#related-reviews').slideDown(1000);
            if (window.location.pathname === '/blank') {
                $('#related-reviews').css('display', 'block');
                $('#related-sort').removeClass('hidden');
                abstractRelatedReviews = $($.parseHTML(msg['data'])).filter('#related_review_items');
            }
        }
        if (msg['section'] === 'related_reviews_update') {
            $('#related_review_items').html(msg['data']);

        }
        if (msg['section'] === 'rel_trials') {
            var rel_container = $('#rel_trials_container');
            if (rel_container.is(':empty')) {
                rel_container.html(msg['data']);
                rel_container.slideDown(2000);
            } else {
                var node = $.parseHTML(msg['data']);
                var replacement = $(node).filter('#accordion-rel');
                $('#accordion-rel').replaceWith(replacement);
                $('#accordion-rel').slideDown(2000);
            }
            var size_li = $('#accordion-rel').children('div.card').length;
            var x = 10;
            $('#accordion-rel div.card').hide();
            $('#accordion-rel div.card:lt(' + x + ')').show();

            $('#load_more_rel').click(function () {
                x = (x + 5 <= size_li) ? x + 5 : size_li;
                $('#accordion-rel div.card:lt(' + x + ')').show();
                if (x === size_li) {
                    $('#load_more_rel').hide();
                }
            });
            $('.upvote').each(function () {
                $(this).upvote({
                    callback: upvote_callback
                });
            });
            $('.rel').removeClass('active');
            $('#' + msg['sort'] + '.rel').addClass('active');
        }
        if (msg['section'] === 'incl_trials') {
            var node = $.parseHTML(msg['data']);
            var replacement = $(node).filter('#accordion-incl');


            var incl_container = $('#incl_trials_container');
            if (incl_container.is(':empty') || $('#accordion-incl').length === 0 || replacement.length === 0) {
                incl_container.html(msg['data']);
                incl_container.slideDown(3000);
            } else {
                if (window.location.pathname === '/blank') {
                    $('#incl_trials_container').html(msg['data']);
                } else $('#accordion-incl').replaceWith(replacement);
            }
            var size_li = $('#accordion-incl').children('div.card').length;
            var x = 20;
            if (size_li <= x) {
                $('#load_more_incl').hide();
            }
            $('#accordion-incl div.card').hide();
            $('#accordion-incl div.card:lt(' + x + ')').show();
            $('#load_more_incl').click(function () {
                x = (x + 5 <= size_li) ? x + 5 : size_li;
                $('#accordion-incl div.card:lt(' + x + ')').show();
                if (x === size_li) {
                    $('#load_more_incl').hide();
                }
            });
            if (msg['sort']) {
                $('.incl').removeClass('active');
                $('#' + msg['sort'] + '.incl').addClass('active');
            }


            if (window.location.pathname === '/blank') {
                replacement.children().each(function (_, nct) {
                    var nct_id = $(nct).attr('id').substring(6);

                    $(`#rel_trials_container #panel_${nct_id}`).fadeOut(1000, () => $(`#rel_trials_container #panel_${nct_id}`).detach());
                });

                if ($('#rel-sort-trials').prop('checked')) {

                    socket.emit('refresh_related', {
                        trials: $('#accordion-incl .panel').toArray().map(d => d.id.substring(6))
                    });
                }
            }
        }
        if (msg['section'] === 'no_results') {
            $('#review-data-container').html(msg['data']);
            $('#review-data-container').slideDown(1000);
            $('#review-trials-container').empty();
            $('.progress_div').slideUp(1000);
        }
    });
    if (document.URL.indexOf('browse') > -1) {
        const browseVerified = window.localStorage.getItem('browseVerified') === 'true';

        $('#verified-only').on('change', e => {
            const state = $(e.target).prop('checked');
            window.localStorage.setItem('browseVerified', state);

            $.ajax({
                url: '/category_counts',
                data: {
                    onlyVerified: state ? 1 : 0
                },
                success: function (data) {
                    $('.list-group-item .badge').text('0').parent().addClass('hidden');
                    data = JSON.parse(data)['data'];
                    for (var i = 0; i < data.length; i++) {
                        $('#' + data[i]['code']).text(data[i]['count']).parent().removeClass('hidden');
                    }

                }
            });
        }).prop('checked', browseVerified).trigger('change');

    } else if (document.URL.indexOf('category') > -1) {
        var addr = document.URL.split('/');
        const browseVerified = window.localStorage.getItem('browseVerified') === 'true';

        $('#verified-only').on('change', e => {
            const state = $(e.target).prop('checked');
            window.localStorage.setItem('browseVerified', state);
            $.ajax({
                url: '/condition_counts',
                type: 'POST',
                contentType: 'application/json;charset=UTF-8',
                data: JSON.stringify({
                    'category': addr[addr.length - 1],
                    onlyVerified: state ? 1 : 0
                }),
                success: function (data) {
                    $('.list-group-item .badge').text('0').parent().addClass('hidden');
                    data = JSON.parse(data)['data'];
                    for (var i = 0; i < data.length; i++) {
                        $('#condition_' + data[i]['id']).text(data[i]['count']).parent().removeClass('hidden');
                    }
                }
            });
        }).prop('checked', browseVerified).trigger('change');

    } else if (document.URL.indexOf('condition') > -1) {
        const browseVerified = window.localStorage.getItem('browseVerified') === 'true';
        $('#verified-only').on('change', e => {
            const state = $(e.target).prop('checked');
            window.localStorage.setItem('browseVerified', state);
            $('.unverified').parent().toggleClass('hidden', state);


        }).prop('checked', browseVerified).trigger('change');
    }
    socket.on('my_response', function (msg) {
        if (document.URL.indexOf('search') >= 0) {
            $(document).ready(function () {

                socket.emit('search', {'review_id': getUrlParameter('searchterm')});
                $('.progress_div').slideDown(1000);
            });
        }
        var url = window.location.href;
        if (window.location.pathname === '/saved') {
            $('.delete-ftext').on('click', e => {
                const idx = $(e.target).attr('id').substr(4);

                $.ajax({
                    url: '/deleteftext',
                    method: 'post',
                    contentType: 'application/json;charset=UTF-8',
                    data: JSON.stringify({
                        review_id: idx
                    }),
                    success: () => {
                        $(e.target).parents('.list-group-item').remove();
                    },
                    error: err => {
                        console.log(err);
                    }
                });
            });
        }
        if (window.location.pathname === '/') {
            $.ajax({
                url: '/data_summary',
                type: 'GET',
                contentType: 'application/json;charset=UTF-8',
                success: function (data) {
                    data = JSON.parse(data)['data'];
                    $('#link_counts').html(
                        `<div><a href="/browse">
                            ${numberWithCommas(data['reviews'])}
                            <small style="color: inherit !important;"> systematic reviews</small>
                            </a>
                            <small> and </small>
                            ${numberWithCommas(data['trials'])}
                            <small> included trials</small>
                        </div>
                        <div>
                            ${numberWithCommas(data['links'])} <small>connections between systematic reviews and trial registrations</small>
                        </div>
                        <div>
                            ${numberWithCommas(data['verified'])} <small>human-verified systematic reviews</small>
                        </div>
                      
                        <div style="font-size: 1.2rem; margin-top:1rem">
                            Data updated: <span class="has-tooltip">${moment(data['updated']).fromNow()}<span class="tooltiptext">${moment(data['updated']).format('LLL')}</span></span>
                        </div>
                        `
                    );
                    $('#link_counts').fadeIn(1000);
                }
            });


        } else if (window.location.pathname === '/blank') {
            $(document).ready(function () {


                $(document).on('change', '#related-sort input', e => {
                    const idx = $(e.target).attr('id');
                    if (idx === 'rel-sort-abstract') {
                        $('#related_review_items').html(abstractRelatedReviews);
                    } else {

                        socket.emit('refresh_related', {
                            trials: $('#accordion-incl .panel').toArray().map(d => d.id.substring(6))
                        });
                    }
                });

                const idx = getUrlParameter('id');
                if (idx) {

                    let prev_abstract = $('#free_text').val();
                    $('#free_text').on('blur', debounce(e => {
                        const abstract = $(e.target).val();
                        if (abstract && abstract !== prev_abstract) {
                            $('#abstract-saved').text('Saved').removeClass('text-danger').addClass('text-success');
                            prev_abstract = abstract;
                            $('#progress_txt').text('Refreshing Recommended Trials...');
                            $('#top-progress').slideDown(1000);
                            socket.emit('freetext_trials', {'review_id': idx, abstract});
                        }
                    }, 3000, true)).on('keyup', e => {
                        const abstract = $(e.target).val();
                        if (abstract && abstract !== prev_abstract) {
                            $('#abstract-saved').text('Not Saved').addClass('text-danger').removeClass('text-success');
                        } else if (abstract === prev_abstract) {
                            $('#abstract-saved').text('Saved').removeClass('text-danger').addClass('text-success');
                        }
                    });

                    let prev_title = $('#free_text_title').val();
                    $('#free_text_title').on('blur', debounce(e => {
                        const title = $(e.target).val();
                        if (title && title !== prev_title) {
                            $('#title-saved').text('Saved').removeClass('text-danger').addClass('text-success');
                            prev_title = title;
                            $.ajax({
                                url: '/updateftexttitle',
                                method: 'post',
                                contentType: 'application/json;charset=UTF-8',
                                data: JSON.stringify({review_id: getUrlParameter('id'), title})
                            });
                        }
                    }, 3000, true)).on('keyup', e => {
                        const title = $(e.target).val();
                        if (title && title !== prev_title) {
                            $('#title-saved').text('Not Saved').addClass('text-danger').removeClass('text-success');
                        } else if (title === prev_title) {
                            $('#title-saved').text('Saved').removeClass('text-danger').addClass('text-success');
                        }
                    });


                    $('#top-progress').slideDown(1000);

                    socket.emit('freetext_trials', {'review_id': idx});
                }
            });
        }

    });
    $('#forgot-password').on('click', e => {
        e.preventDefault();
        $('#login-tabs a[href="#reset"]').tab('show');
    });

    socket.on('search_update', function (msg) {

        $('#progress_txt').text(msg['msg']);
        if (msg['msg'] === 'complete') {
            $('.progress-div').attr('style', 'display:none;');
        }
    });
    socket.on('search_res', function (msg) {
        $('#progress_txt').text(msg['msg']);

    });

    socket.on('docsim_update', function (msg) {
        if (!$('.progress_basicbot').is(':visible')) {
            $('.progress_basicbot').slideDown(1000);
        }
        $('#progress_txt_basicbot').text(msg['msg']);
        if (msg['msg'].indexOf('complete') > -1) {
            socket.emit('refresh_trials', {
                'review_id': getUrlParameter('searchterm'),
                'type': 'rel',
                'plot': true
            });
            $('.progress_basicbot').delay(1000).slideUp(2000);
        }

    });
    socket.on('crossrefbot_update', function (msg) {
        if (!$('.progress_crossrefbot').is(':visible')) {
            $('.progress_crossrefbot').slideDown(1000);
        }
        $('#progress_txt_crossrefbot').text(msg['msg']);
        if (msg['msg'].indexOf('complete') > -1) {
            socket.emit('refresh_trials', {
                'review_id': getUrlParameter('searchterm'),
                'type': 'incl',
                'plot': true
            });
            $('.progress_crossrefbot').delay(1000).slideUp(2000);
        }

    });
    socket.on('cochranebot_update', function (msg) {

        if (!$('.progress_cochranebot').is(':visible')) {
            $('.progress_cochranebot').slideDown(1000);
        }
        $('#progress_txt_cochranebot').text(msg['msg']);
        if (msg['msg'].indexOf('complete') > -1) {
            socket.emit('refresh_trials', {
                'review_id': getUrlParameter('searchterm'),
                'type': 'incl',
                'plot': true
            });
            if (msg['refresh_both']) {
                socket.emit('refresh_trials', {
                    'review_id': getUrlParameter('searchterm'),
                    'type': 'rel',
                    'plot': true
                });
            }
            $('.progress_cochranebot').delay(1000).slideUp(2000);
        }

    });
    socket.on('basicbot2_update', function (msg) {
        if (!$('.progress_basicbot2').is(':visible')) {
            $('.progress_basicbot2').slideDown(1000);
        }
        $('#progress_txt_basicbot2').text(msg['msg']);
        if (msg['msg'].indexOf('complete') > -1) {
            socket.emit('refresh_trials', {
                'review_id': getUrlParameter('searchterm'),
                'type': 'rel',
                'plot': true
            });
            $('.progress_basicbot2').delay(1000).slideUp(2000);
        }

    });
    socket.on('new_page', function (msg) {
        // todo replace this with something faster and more scalable
        $('.pg_content').html(msg['data']);
    });

    function getUrlParameter(sParam) {
        var sPageURL = decodeURIComponent(window.location.search.substring(1)),
            sURLVariables = sPageURL.split('&'),
            sParameterName,
            i;
        for (i = 0; i < sURLVariables.length; i++) {
            sParameterName = sURLVariables[i].split('=');
            if (sParameterName[0] === sParam) {
                return sParameterName[1] === undefined ? true : sParameterName[1];
            }
        }
    }

    var upvote_callback = function (data) {
        $.ajax({
            url: '/vote',
            type: 'post',
            contentType: 'application/json;charset=UTF-8',
            data: JSON.stringify({
                id: data.id,
                up: data.upvoted,
                down: data.downvoted,
                star: data.starred,
                review: getUrlParameter('searchterm')
            }),
            error: function (data2) {
                var modal = $('#myModal');
                modal.find('.modal-body p').text(data2['responseText']);
                modal.modal();
                if (data.upvoted) {
                    $('#' + data.id + '_vote > a.upvote').removeClass('upvote-on');
                } else {
                    $('#' + data.id + '_vote > a.downvote').removeClass('downvote-on');
                }
            },
            success: function (data1) {
                var result = JSON.parse(data1);
                $('#panel_' + data.id + ' a.nicknames').html(result['voters']);
            }
        });
    };
    $('div.upvote').upvote({
        callback: upvote_callback
    });

    function move_rel_incl(nct_id) {
        disable_elements();
        var panel = $('#panel_' + nct_id);
        var category = 'incl';
        relevant_included(nct_id, function (data) {
            panel.fadeOut('slow', function () {
                panel.remove();
                var result = JSON.parse(data);

                socket.emit('refresh_trials', {
                    'review_id': getUrlParameter('searchterm'),
                    'type': 'incl',
                    'plot': true
                });
                socket.emit('trigger_basicbot2', {
                    'review_id': getUrlParameter('searchterm')
                });
                $('#alert-place-' + category).show();
                $('#alert-place-' + category).html('<div class="alert alert-success "> <strong>Thank you! </strong>' + result['message'] + '</div>');
                $('#alert-place-' + category).delay(3000).fadeOut('slow');
            });
            enable_elements();
        });
    }

    $(document).on('click', '.rel_incl', function (e) {
        var nct_id = e.target.id.substring(0, 11);
        move_rel_incl(nct_id);
    });
    $(document).on('click', '.rec_rel_incl', function (e) {
        var nct_id = e.target.id.substring(0, 11);
        var $panel = $('#panel_' + nct_id);
        var category = 'incl';
        $('#' + nct_id + '_movincl').css('visibility', 'hidden');
        submitTrial(nct_id, 'included', true, data => {


            $panel.fadeOut('slow', function () {

                socket.emit('refresh_trials', {
                    'ftext': true,
                    'review_id': getUrlParameter('id'),
                    'type': 'incl',
                    'plot': true,
                    'rec_trials': $('#accordion-rel').children('.card').toArray().map(div => $(div).attr('id').substring(6))
                });
                $panel.detach();
            });

        });


    });
    $(document).on('click', '.save_review', function (e) {
        var val = true;
        var review_id = this.id;
        if (typeof ($(this).attr('active')) === 'undefined') {
            val = false;
        }

        $.ajax({
            url: '/save_review',
            type: 'post',
            contentType: 'application/json;charset=UTF-8',
            data: JSON.stringify({
                review_id: review_id,
                value: val
            }),
            error: function (data2) {
                var modal = $('#myModal');
                modal.find('.modal-body p').text(data2['responseText']);
                modal.modal();
            }
        });
    });

    function move_incl_rel(nct_id) {
        disable_elements();
        var category = 'incl';
        var panel = $('#panel_' + nct_id);
        included_relevant(nct_id, function (data) {
            if ($('#accordion-incl > .panel').length === 1) {

                socket.emit('refresh_trials', {
                    'review_id': getUrlParameter('searchterm'),
                    'type': 'incl',
                    'sort': 'net_upvotes',
                    'plot': false
                });
            } else {
                panel.fadeOut('slow', function () {
                    panel.remove();

                });
            }
            var result = JSON.parse(data);

            socket.emit('refresh_trials', {
                'review_id': getUrlParameter('searchterm'),
                'type': 'rel',
                'plot': true
            });
            $('#alert-place-' + category).show();
            $('#alert-place-' + category).html('<div class="alert alert-success "> <strong>Thank you! </strong>' + result['message'] + '</div>');
            $('#alert-place-' + category).delay(3000).fadeOut('slow', function () {
                enable_elements();
            });
        });
    }

    function calc_completeness() {
        var rel_trials = 0;
        var rel_participants = 0;
        $('.rel-check:checked').each(function () {
            rel_trials += 1;
            if (parseInt($(this).attr('value'))) {
                rel_participants += parseInt($(this).attr('value'));
            }
        });
        $('#num_rel_trials').text(rel_trials);
        $('#part_rel_trials').text(rel_participants);
    }

    $(document).on('click', '#reset_cmp', function (e) {
        $('.rel-check:checked').each(function () {
            $(this).prop('checked', false);
        });
        calc_completeness();
    });
    $(document).on('click', '.sort .btn', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var order = $(this).attr('id');
        var side = '';
        if ($(this).hasClass('incl')) {
            side = 'incl';
        } else {
            side = 'rel';
        }
        console.log(order, side);
        socket.emit('refresh_trials', {
            'review_id': getUrlParameter('searchterm'),
            'type': side,
            'sort': order,
            'plot': false
        });
    });
    $(document).on('click', '#cmp_btn', function (e) {
        $('#completeness_val').css('visibility', 'visible');
        $('#cmp_btn').css('visibility', 'hidden');
        $('#reset').css('visibility', 'visible');
        $('.form-check-input').css('visibility', 'visible');
        calc_completeness();
    });
    $(document).on('click', '.btn-incl-cmp', function (e) {
        var complete = e.target.value;
        update_included_complete(complete, function (data) {
            $('.btn-incl-cmp').fadeOut(1000);
            var result = JSON.parse(data);
            $('#alert-place-incl').html('<div class="alert alert-success">  <strong>' + result['message'] + '</strong></div>');
            $('#alert-place-incl').delay(3000).fadeOut('slow');
            $('#accordion-incl').slideUp(2000);
            socket.emit('refresh_trials', {
                'review_id': getUrlParameter('searchterm'),
                'type': 'incl',
                'plot': false
            });
            if (complete === 'True') {
                socket.emit('trigger_basicbot2', {
                    'review_id': getUrlParameter('searchterm')
                });
                $('.rel_incl').css('visibility', 'hidden');
                $('.btn-incl-cmp').val('False');
                $('.btn-incl-cmp').html('This list is incomplete');
            } else {
                $('.rel_incl').css('visibility', 'visible');
                $('.btn-incl-cmp').val('True');
                $('.btn-incl-cmp').html('This list is complete');
            }
            $('.btn-incl-cmp').fadeIn(1000);
        });
    });
    $(document).on('change', '.form-check-input:checkbox', function (e) {
        calc_completeness();
    });

    function disable_elements() {
        $('.nct-submit').attr('disabled', true);
        $('.upvote').attr('disabled', true);
        $('.downvote').attr('disabled', true);
        $('.dismiss').attr('disabled', true);
        $('.btn-incl-cmp').attr('disabled', true);
        $('.rel_incl').attr('disabled', true);
    }

    function enable_elements() {
        $('.nct-submit').attr('disabled', false);
        $('.upvote').attr('disabled', false);
        $('.downvote').attr('disabled', false);
        $('.dismiss').attr('disabled', false);
        $('.btn-incl-cmp').attr('disabled', false);
        $('.rel_incl').attr('disabled', false);
    }

    $(document).on('click', '.nct-submit', function (e) {
        var re_nct = new RegExp('^(NCT|nct)[0-9]{8}$');
        var category = e.target.name;
        var nct_id = $('#' + category + '-id').val().trim();


        if (re_nct.test(nct_id)) {
            var accordion = $('#accordion-' + category);
            disable_elements();
            submitTrial(nct_id, (category.indexOf('incl') > -1 ? 'included' : 'relevant'), window.location.pathname === '/blank', function (data) {
                var result = JSON.parse(data);
                if (result['success'] == true) {
                    accordion.fadeOut('slow');
                    $('#alert-place-' + category).html('<div class="alert alert-success">  <strong>Thank you! </strong>' + result['message'] + '</div>');
                    $('#alert-place-' + category).show();
                    $('#alert-place-' + category).delay(3000).fadeOut('slow', function () {
                        enable_elements();
                    });
                    $('#accordion-' + category).prepend('');

                    socket.emit('refresh_trials', {
                        'ftext': window.location.pathname === '/blank',
                        'review_id': getUrlParameter('searchterm') || getUrlParameter('id'),
                        'type': category,
                        'plot': true,
                        'rec_trials': $('#accordion-rel').children('.card').toArray().map(div => $(div).attr('id').substring(6))
                    });

                    if (category.indexOf('incl') > -1 && window.location.pathname !== '/blank') {
                        socket.emit('trigger_basicbot2', {
                            'review_id': getUrlParameter('searchterm')
                        });
                    }
                } else {
                    var to_move = $('#panel_' + nct_id);
                    to_move.parent().prepend(to_move);
                    if (to_move.is(':hidden')) {
                        to_move.show();
                    }
                    to_move[0].scrollIntoView({behaviour: 'smooth'});
                    $('#panel_' + nct_id + '> .panel-heading').effect('highlight', {}, 3000);
                    if (result['move']) {
                        $('#alert-place-' + category).html('<div class="alert alert-info "> <strong>Uh oh! </strong>' + result['message'] + '   <a class="btn btn-xs btn-primary pull-right move-trial">Move to this list</a></div>');
                    } else {
                        $('#alert-place-' + category).html('<div class="alert alert-info "> <strong>Uh oh! </strong>' + result['message'] + '  </div>');
                    }
                    $('#alert-place-' + category).fadeIn(1000);
                    $('#alert-place-' + category).delay(3000).fadeOut(1000, function () {
                        enable_elements();
                    });
                    $(document).on('click', '.move-trial', function (e) {
                        if (category === 'incl') {
                            $('#alert-place-' + category).html('');
                            move_rel_incl(nct_id);
                        } else if (category === 'rel') {
                            $('#alert-place-' + category).html('');
                            move_incl_rel(nct_id);
                        }
                    });
                }
            });
        } else {
            $('#alert-place-' + category).html('<div class="alert alert-warning "><strong>Uh oh! </strong>Please enter a valid ClinicalTrials.gov registry ID</div>');
            $('#alert-place-' + category).fadeIn(400, function () {
                $('#alert-place-' + category).delay(2000).fadeOut('slow', function () {
                    enable_elements();
                });
            });
        }
    });
    $(document).on('click', '.row .dismiss', function (e) {
        var nct_id = e.target.id.substring(8);

        if (window.location.pathname === '/blank') {
            removeTrial(nct_id, getUrlParameter('id'));
            $(
                `#${nct_id}_movincl`
            ).css('visibility', 'visible');
            $(e.target).parents('.panel').remove();

            if ($('#rel-sort-trials').prop('checked')) {

                socket.emit('refresh_related', {
                    trials: $('#accordion-incl .panel').toArray().map(d => d.id.substring(6))
                });
            }

            return;
        }
        move_incl_rel(nct_id);
    });

    $('#recommender-new').on('click', e => {
        e.preventDefault();

        $.ajax({
            url: '/createftext',
            method: 'post',
            success: data => {
                console.log(data);
                window.location.href =
                    `/blank?id=${JSON.parse(data)['idx']}`
                ;
            }
        });
    });

    $('#recommender-titlebar').on('click', e => {
        e.preventDefault();

        $.ajax({
            url: '/recent_ftext_review',
            success: data => {
                window.location.href =
                    `/blank?id=${JSON.parse(data)['idx']}`
                ;
            }
        });
    });

    function update_included_complete(complete, callback) {
        $.ajax({
            url: '/included_complete',
            type: 'post',
            contentType: 'application/json;charset=UTF-8',
            data: JSON.stringify({
                review_id: getUrlParameter('searchterm'),
                value: complete
            }),
            error: function (data2) {
                var modal = $('#myModal');
                modal.find('.modal-body p').text(data2['responseText']);
                modal.modal();
            },
            success: function (data) {
                callback(data);
            }
        });
    }

    function included_relevant(nct_id, callback) {
        $.ajax({
            url: '/included_relevant',
            type: 'post',
            contentType: 'application/json;charset=UTF-8',
            data: JSON.stringify({
                nct_id: nct_id,
                review: getUrlParameter('searchterm')
            }),
            success: function (data) {
                callback(data);
            },
            error: function (data2) {
                var modal = $('#myModal');
                modal.find('.modal-body p').text(data2['responseText']);
                modal.modal();
            }
        });
    }

    function relevant_included(nct_id, callback) {
        $.ajax({
            url: '/relevant_included',
            type: 'post',
            contentType: 'application/json;charset=UTF-8',
            data: JSON.stringify({
                nct_id: nct_id,
                review: getUrlParameter('searchterm')
            }),
            success: function (data) {
                callback(data);
            },
            error: function (data2) {
                var modal = $('#myModal');
                modal.find('.modal-body p').text(data2['responseText']);
                modal.modal();
            }
        });
    }

    function removeTrial(nct_id, review_id) {
        $.ajax({
            url: '/removeftexttrial',
            type: 'post',
            contentType: 'application/json;charset=UTF-8',
            data: JSON.stringify({
                nct_id,
                review_id
            }),
            success: function (data) {

            },
            error: function (data2) {

            }
        });
    }

    function submitTrial(id, relationship, userCreated = false, callback) {
        disable_elements();
        let review_id = getUrlParameter('searchterm');
        let url = '/submittrial';

        if (userCreated) {
            review_id = getUrlParameter('id');
            url = '/submitftexttrial';
        }

        $.ajax({
            url,
            type: 'post',
            contentType: 'application/json;charset=UTF-8',
            data: JSON.stringify({
                nct_id: id,
                relationship: relationship,
                review: review_id
            }),
            success: function (data) {
                callback(data);
                enable_elements();
            },
            error: function (data2) {
                var modal = $('#myModal');
                modal.find('.modal-body p').text(data2['responseText']);
                modal.modal();
                enable_elements();
            }
        });
    }

    function getPlot(callback) {
        $.ajax({
            url: '/plot',
            type: 'post',
            contentType: 'application/json;charset=UTF-8',
            success: function (data) {
                callback(data);
            }
        });
    }
});

