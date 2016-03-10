openerp.document_caldav = function(instance){
    var module = instance.web.search;

    module.CustomFilters.include({
        toggle_filter: function (filter, preventSearch) {
            this._super(filter, preventSearch);
            var current_id = this.view.query.pluck('_id');
            var url = '';
            if (current_id.length) {
                url = this.session.server + '/webdav/' +
                    this.session.db + '/calendar/users/' +
                    this.session.username + '/a/m-' + this.view.model +
                    '/filtered-' + current_id[0] + '/';
            }
            $('#filter_caldav_url').val(url);
        }
    });
};
