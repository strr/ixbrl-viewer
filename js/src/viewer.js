import $ from 'jquery'

export function Viewer(iframe) {
    this._iframe = iframe;
    this._contents = iframe.contents();
    this._onSelectHandlers = [];

    this._preProcessiXBRL($("body", iframe.contents()).get(0));
    this._applyStyles();
    this._bindHandlers();
    this.scale = 1;
    
}

function localName(e) {
    if (e.indexOf(':') == -1) {
        return e
    }
    else {
        return e.substring(e.indexOf(':') + 1)
    }
}

Viewer.prototype._preProcessiXBRL = function(n, inHidden) {
  var elt;
  if(n.nodeType == 1 && (localName(n.nodeName) == 'NONNUMERIC' || localName(n.nodeName) == 'NONFRACTION')) {
    var wrapper = "span";
    var nn = n.getElementsByTagName("*");
    for (var i = 0; i < nn.length; i++) {
      if($(nn[i]).css("display") === "block") {
        wrapper = 'div';
        break;
      }
    }
    var elt;
    if (localName(n.nodeName) == 'NONFRACTION') {
      $(n).wrap('<' + wrapper + ' class="ixbrl-element ixbrl-element-nonfraction"></' + wrapper + '>');
      $(n).parent().data('ivid', n.getAttribute("id"));
      if(inHidden) {
        elt = $(n).parent().clone();
      }
    }
    if (localName(n.nodeName) == 'NONNUMERIC') {
      $(n).wrap('<' + wrapper + ' class="ixbrl-element ixbrl-element-nonnumeric"></' + wrapper + '>');
      $(n).parent().data('ivid', n.getAttribute("id"));
      if(inHidden) {
        elt = $(n).parent().clone();
      }
    }
    if (elt) {
      var concept = n.getAttribute("name");
      if(elt.children().first().text() == "") {
        elt.children().first().html("<i>no content</i>");
      }
      var tr = $("<tr></tr>").append("<td><div title=\"" + concept + "\">" + concept + "</div></td>").append($(elt).wrap("<td></td>").parent());
      $("#ixbrl-inspector-hidden-facts-table-body").append(tr);
    }
  }
  else if(n.nodeType == 1 && localName(n.nodeName) == 'HIDDEN') {
    inHidden = true;
  }
  for (var i=0; i < n.childNodes.length; i++) {
    this._preProcessiXBRL(n.childNodes[i], inHidden);
  }
}

Viewer.prototype._applyStyles = function () {
    $("<style>")
        .prop("type", "text/css")
        .html(require('css-loader!less-loader!./iframe.less').toString())
        .appendTo($("head", this._iframe.contents()));
}


Viewer.prototype._selectAdjacentTag = function (offset) {
    var elements = $(".ixbrl-element", this._contents);
    var current = $(".ixbrl-selected", this._contents);
    var next;
    if (current.length == 1) {
        next = elements.eq((elements.index(current.first()) + offset) % elements.length);
    }
    else if (offset > 0) {
        next = elements.first();
    } 
    else {
        next = elements.last();
    }
        
    this.showAndSelectElement(next);
}

Viewer.prototype._bindHandlers = function () {
    var viewer = this;
    $('.ixbrl-element', this._contents).click(function (e) {
        e.stopPropagation();
        viewer.selectElement($(this));
    });
    $('#iframe-container .zoom-in').click(function () { viewer.zoomIn() });
    $('#iframe-container .zoom-out').click(function () { viewer.zoomOut() });
}

Viewer.prototype.selectNextTag = function () {
    this._selectAdjacentTag(1);
}

Viewer.prototype.selectPrevTag = function () {
    this._selectAdjacentTag(-1);
}

Viewer.prototype.scrollIfNotVisible = function(e) {
    var viewTop = this._iframe.contents().scrollTop();
    var viewBottom = viewTop + this._iframe.height();
    var eTop = e.offset().top;
    var eBottom = eTop + e.height();
    if (eTop < viewTop || eBottom > viewBottom) {
        this._iframe.contents().scrollTop(e.offset().top - this._iframe.height()/2);
    }
}

Viewer.prototype.showAndSelectElement = function(e) {
    this.scrollIfNotVisible(e);
    this.selectElement(e);
}

Viewer.prototype.selectElement = function (e) {
    e.closest("body").find(".ixbrl-element").removeClass("ixbrl-selected");
    e.closest("body").find(".ixbrl-element").removeClass("ixbrl-related");
    e.addClass("ixbrl-selected");
    var id = e.data('ivid');
    $.each(this._onSelectHandlers, function (i, handler) {
        handler(id);
    });
}

Viewer.prototype.highlightRelatedFact = function (f) {
    var e = this.elementForFact(f);
    e.addClass("ixbrl-related");
}

Viewer.prototype.elementForFact = function (fact) {
    return $('.ixbrl-element', this._contents).filter(function () { return $(this).data('ivid') == fact.id }).first();
}

Viewer.prototype.showAndSelectFact = function (fact) {
    this.showAndSelectElement(this.elementForFact(fact));
}

Viewer.prototype.onSelect = function (f) {
    this._onSelectHandlers.push(f);
}

Viewer.prototype.highlightAllTags = function (on) {
    if (on) {
        $(".ixbrl-element", this._contents).addClass("ixbrl-highlight");
    }
    else {
        $(".ixbrl-element", this._contents).removeClass("ixbrl-highlight");
    }
}

Viewer.prototype._zoom = function () {
    var viewTop = this._contents.scrollTop();
    var height = $("html",this._contents).height();
    $('body', this._contents).css('zoom',this.scale);

    var newHeight = $("html", this._contents).height();
    this._contents.scrollTop(newHeight * (viewTop)/height );
    

}

Viewer.prototype.zoomIn = function () {
    this.scale *= 1.1;
    this._zoom();
}
Viewer.prototype.zoomOut = function () {
    this.scale /= 1.1;
    this._zoom();
}
