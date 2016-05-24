$(document).ready(function() {          
    $('.detectButton').each(function(){
        $(this).click(function(){
            var note = $('<div id="submitdialog"></div>').appendTo(".container");
            var overlay = $('<div id="turkic_overlay"></div>').appendTo(".container");
            note.html("Running Neural Network...");
        });
    });
});

$(document).ready(function() {          
    $("#train_from_submit").click(function(){
        loading();
        var note = $("#submitdialog")
        var overlay = $('<div id="turkic_overlay"></div>').appendTo(".container");
        note.html("Apply Perceptural Hashing to Remove Similar Frames...");
    });
});
