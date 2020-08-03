#![feature(proc_macro_hygiene, decl_macro)]

#[macro_use] extern crate rocket;
#[macro_use] extern crate rocket_contrib;

use rocket::Outcome;

use rocket::request::{self, Request, FromRequest};
use rocket::response::status::Unauthorized;
use crate::rocket_contrib::databases::redis::Commands;
use rocket_contrib::databases::redis;
use std::result::Result;

#[database("redis_db")]
struct DbConn(redis::Connection);


struct Headers {
    XForwardedFor: String,
    XOriginalURI: String,
}


#[derive(Debug)]
enum HeaderError {
    Missing
}

impl<'a, 'r> FromRequest<'a, 'r> for Headers {
    type Error = HeaderError;
    fn from_request(request: &'a Request<'r>) -> request::Outcome<Self, Self::Error> {
        let x_forwarded_for = request.headers().get("X-Request-Address").next().unwrap();
        let x_original_uri = request.headers().get("X-Original-URI").next().unwrap();
        Outcome::Success(Headers { XForwardedFor: x_forwarded_for.to_string(), XOriginalURI: x_original_uri.to_string() })
    }
}


#[get("/auth")]
fn index(redis: DbConn, headers: Headers) -> Result<String, Unauthorized<Result<(), ()>>> {
   let mut split = headers.XOriginalURI.split("/");
   let components: Vec<&str> = split.collect();
   let session_id = components[2];
   let user_id = components[3];
   // println!("{}", session_id);
   // println!("{}", user_id);
   let exists = redis::cmd("exists").arg(session_id).query(&*redis).unwrap();
   if exists {
        let fetched_session_id: Result<String, _> = redis::cmd("get").arg(session_id).query(&*redis);
        let fetched_session_id = match fetched_session_id {
            Ok(new_session_id) => new_session_id,
            Err(e) => return Err(Unauthorized(None)),
        };
        // println!("Got session ID from Redis");
        let str = format!("{}_user_id", session_id);
        // println!("{}", str);
        let fetched_user_id: Result<String, _> = redis::cmd("get").arg(str).query(&*redis);;
        let fetched_user_id  = match fetched_user_id {
            Ok(new_fetched_user_id) => new_fetched_user_id,
            Err(e) => return Err(Unauthorized(None)),
        };
        // println!("Got user ID from Redis");
        // println!("{}", fetched_user_id);
        // println!("{}", fetched_session_id);
        if fetched_session_id == headers.XForwardedFor && fetched_user_id == user_id {
            return Ok("hello".to_string());
        } else {
            return Err(Unauthorized(None));
        }
   } else {
        return Err(Unauthorized(None));
   }
}


fn main() {
    let client = redis::Client::open("redis://127.0.0.1/").unwrap();
    let con = client.get_connection().unwrap();
    rocket::ignite().attach(DbConn::fairing()).mount("/", routes![index]).launch();
}
