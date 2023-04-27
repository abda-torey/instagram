"use strict";
window.addEventListener("load", function () {
  var logoutButton = document.getElementById("logout");
  var loginButton = document.getElementById("login");
  if (logoutButton) {
    logoutButton.onclick = function () {
      // ask firebase to sign out the user
      firebase.auth().signOut();
      window.location.href = "/";
      document.cookie = "token=;path=/";
    };
  }
  if (loginButton) {
    loginButton.onclick = function () {
      var ui = new firebaseui.auth.AuthUI(firebase.auth());
      ui.start("#firebase-auth-container", uiConfig);
      document.cookie = "token=" + token + ";path=/";
    };
  }
  var uiConfig = {
    signInSuccessUrl: "/",
    signInOptions: [firebase.auth.EmailAuthProvider.PROVIDER_ID],
    callbacks: {
      signInSuccessWithAuthResult: function (authResult, redirectUrl) {
        authResult.user.getIdToken().then(function (token) {
          document.cookie = "token=" + token + ";path=/";
        });
        return true;
      },
    },
  };

  firebase.auth().onAuthStateChanged(
    function (user) {
      if (user) {
        var name = user.displayName;
        document.cookie = "name=" + name;
        console.log("Signed in as ", user.displayName, user.email);
        user.getIdToken().then(function (token) {
          document.cookie = "token=" + token + ";path=/";
        });
      } else {
        var ui = new firebaseui.auth.AuthUI(firebase.auth());
        ui.start("#firebase-auth-container", uiConfig);
        document.getElementById("login-info").hidden = true;
        document.cookie = "token=;path=/";
      }
    },
    function (error) {
      console.log(error);
      alert("Unable to log in: " + error);
    }
  );
});
