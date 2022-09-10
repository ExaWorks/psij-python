var SELECTOR_TYPES = ["executor-type"];
var SELECTOR_TYPE_DEFAULTS = {"executor-type": "Local"};

function addSelectorType(selectorType, defaultValue) {
    SELECTOR_TYPES.push(selectorType);
    SELECTOR_TYPE_DEFAULTS[selectorType] = defaultValue;
}

function saveChoice(type, value) {
	document.cookie = type + "=" + value;
}

function loadChoice(type, def) {
	if (document.cookie) {
		var all = document.cookie;
		var a = all.split(';');
		for (var i = 0; i < a.length; i++) {
			var cookie = a[i];
			if (cookie.startsWith(type)) {
				var kv = cookie.split('=');
				if (kv[0] == type) {
					return kv[1];
				}
			}
		}
	}
	return def;
}


$(document).ready(function() {
    SELECTOR_TYPES.forEach(function(selectorType) {
        var value = loadChoice(selectorType, SELECTOR_TYPE_DEFAULTS[selectorType]);
        detectAll(selectorType);
        
        initializeSelectors(selectorType, value);
    });
});

function detectAll(selectorType) {
    // we have three types of items:
    //   - selectors, identified by p.<selectorType>-selector, 
    //     which get transformed into select boxes
    //   - simple values, which are spans with the text \"\<&<selectorType>\>\", where 
    //     the backslashed characters are literals
    //   - code blocks with classes <selectorType>-item and <selectorType>-<value>
    // we first tag objects with <selectorType>-item, then iterate over that class
    // and initialize such that simple values and panels bind to the immediately 
    // preceding selector
    // 
    // The reason for all this is correctness, in the sense that one could encounter the 
    // following situation:
    // Selector 1: A, B, C
    //    <&simple_value_1>
    // Selector 2: B, C, D
    //    <&simple_value_2>
    //
    // If "A" is selected in the first selector, we want to only change simple_value_1.
    // Similarly, if "D" is selected in the second selector, we only want to change 
    // simple_value_2. However, if either "B" or "C" are selected in either selector,
    // we want to change both.
    
    $("p." + selectorType + "-selector").addClass(selectorType + "-item");
    $("span").each(function() {
        if ($(this).text() == '"<&' + selectorType + '>"') {
            $(this).addClass(selectorType + "-item").addClass("psij-selector-value");
        }
    });
}

function initializeSelectors(selectorType, defaultValue) {
    var context = {lastValues: null, tabsIndex: 0};
    $("." + selectorType + "-item").each(function() {
        if ($(this).is("p")) {
            // selector
            initializeSelector(context, $(this), selectorType, defaultValue);
        }
        else if ($(this).is("span")) {
            // simple value
            initializeSimpleValue(context, $(this), selectorType, defaultValue);
        }
        else if ($(this).is("div")) {
            // code block
            initializeCodeBlock(context, $(this), selectorType, defaultValue);
        }
        else {
            console.log("Unexpected psij-selector-item object: ", $(this));
        }
    });
}


function globalSelectSelectorValue(selectorType, value) {
    $("select." + selectorType + "-selector option[value=\"" + value + "\"]").prop("selected", true);
    $("input." + selectorType + "-selector[value=\"" + value + "\"]").prop("checked", true);
    $("." + selectorType + "-value").each(function() {
        if ($(this).parent().data("allowed-values").includes(value)) {
            $(this).fadeTo(300, 0.01, function() {
                $(this).html('"' + value.toLowerCase() + '"');
                $(this).fadeTo(300, 1.0);
            });
        }
    });
    $("." + selectorType + "-code-block").each(function() {
        if ($(this).data("allowed-values").includes(value)) {
            // only hide/show if previous switch has this value
            if ($(this).hasClass(selectorType + "-" + value.toLowerCase())) {
                $(this).show();
            }
            else {
                $(this).hide();
            }
        }
    });
}

function initializeSelector(context, $el, selectorType, selectedValue) {
    var text = $el.text();
    var values = text.split(/\s*\/\/\s*/); // split on "//" possible with whitespace around
    
    context.lastValues = values;
    
    if ($el.hasClass("selector-mode-tabs")) {
        initializeSelectorTabs(context, $el, selectorType, values, selectedValue);
    }
    else {
        initializeSelectorDropdown(context, $el, selectorType, values, selectedValue);
    }
}

function initializeSelectorDropdown(context, $el, selectorType, values, selectedValue) {
    var select = $("<select>").addClass(selectorType + "-selector").addClass("psij-selector");
    $el.html($("<label>").text("See example for "));

    values.forEach(function(value) {
        var option = $("<option>").attr("value", value).text(value);
        if (value == selectedValue) {
            option.prop("selected", true);
        }
        option.appendTo(select);
    });
    select.change(function() {
        globalSelectSelectorValue(selectorType, $(this).val());
    });
    $el.addClass("initialized");
    $el.addClass("selector-container-dropdown");
    select.appendTo($el);
}

function initializeSelectorTabs(context, $el, selectorType, values, selectedValue) {
    var i = 0;
    $el.html(""); // remove unparsed labels
    values.forEach(function(value) {
        var input = $("<input></input>")
				.addClass("selector-radio").addClass(selectorType + "-selector")
				.attr("type", "radio")
				.attr("name", "_" + selectorType + "-" + context.tabsIndex)
				.attr("id", "_" + selectorType + "-" + context.tabsIndex + "-" + i)
				.attr("value", value);
		if (value == selectedValue) {
		    input.prop("checked", true);
		}
        input.appendTo($el);
        input.change(function() {
            globalSelectSelectorValue(selectorType, $(this).val());
        });
        var label = $("<label></label>")
				.addClass("selector-label")
				.attr("for", "_" + selectorType + "-" + context.tabsIndex + "-" + i)
				.html(value);
		$el.addClass("initialized");
	    label.appendTo($el);
	    i++;
    });
    context.tabsIndex++;
    $el.addClass("selector-container-tabs");
}



function initializeSimpleValue(context, $el, selectorType, selectedValue) {
    $el.html($("<span>").addClass(selectorType + "-value").text('"' + selectedValue.toLowerCase() + '"'));
    $el.data("allowed-values", context.lastValues);
}

function initializeCodeBlock(context, $el, selectorType, selectedValue) {
    // we add this class so we can quickly iterate through all code blocks when hiding/showing
    $el.addClass(selectorType + "-code-block");
    $el.data("allowed-values", context.lastValues);
    if ($el.hasClass(selectorType + "-" + selectedValue.toLowerCase())) {
        $el.show();
    }
    else {
        $el.hide();
    }
}