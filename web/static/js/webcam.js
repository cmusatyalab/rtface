function sendDetectRequest() {
    // Generate the image data
    var Pic = document.getElementById("canvas").toDataURL("image/jpeg");
    Pic = Pic.replace(/^data:image\/(png|jpg);base64,/, "")

    var model_select = document.getElementById("model_select")
    var model = model_select.options[model_select.selectedIndex].value;
    var render_detection_result=function(resp){
        $('#detectContent').replaceWith("<img src="+resp.responseJSON.img_url+">");
    }

    console.log('model:'+model)
    // Sending the image data to Server
    $.ajax({
        type: 'POST',
        url: '/detect_upload_webcam',
        data: '{ "image_data" : "' + Pic + '","model":"'+model+'"}',
        contentType: 'application/json; charset=utf-8',
        dataType: 'json'}).done(render_detection_result).fail(function(resp){
            $('#detectContent').replaceWith(resp.responseJSON.error_msg)
        });
}

window.onload = function() {
    //Compatibility
    navigator.getUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia;

    var canvas = document.getElementById("canvas"),
        context = canvas.getContext("2d"),
        video = document.getElementById("video"),
        btnStart = document.getElementById("btnStart"),
        btnStop = document.getElementById("btnStop"),
        btnPhoto = document.getElementById("btnPhoto"),
        btnDetect = document.getElementById("detectWebcam"),
        videoObj = {
            video: true,
            audio: true
        };

    btnStart.addEventListener("click", function() {
        var localMediaStream;
        if (navigator.getUserMedia) {
            navigator.getUserMedia(videoObj, function(stream) {              
                video.src = (navigator.webkitGetUserMedia) ? window.URL.createObjectURL(stream) : stream;
                localMediaStream = stream;
            }, function(error) {
                console.error("Video capture error: ", error.code);
            });

            btnStop.addEventListener("click", function() {
                localMediaStream.getVideoTracks()[0].stop();
            });

            btnPhoto.addEventListener("click", function() {
                context.drawImage(video, 0, 0, 320, 240);

            });
        }
    });
};

