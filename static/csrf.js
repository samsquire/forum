async function get_token () {
    var response = await fetch("http://api.lonely-people.com/csrf", {
    method: "POST",
    mode: "cors",
    cache: "no-cache",
    headers: {
        "content-type": "text/plain"
    },
    redirect: "follow",
    body: "",
    credentials: 'include'
});
    return response.text();
}

get_token().then(function (data) {
    for (var form of document.querySelectorAll("form")) {
        var hidden = document.createElement("input");
        hidden.setAttribute("type", "hidden");
        hidden.setAttribute("value", data);
        hidden.setAttribute("name", "_csrf_token");
        form.insertAdjacentElement("afterbegin", hidden);
    }
})
