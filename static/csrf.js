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


var session_id = String(document.location).split("/")[4]
console.log(session_id);
var user_id = String(document.location).split("/")[5]
console.log(user_id);
for (var form of document.forms) {
    form.action = form.action.replace("SESSION", session_id);
    form.action = form.action.replace("USER", user_id);
}

for (var element of document.querySelectorAll("a")) {
    element.href = element.href.replace("SESSION", session_id);
    element.href = element.href.replace("USER", user_id);
};
