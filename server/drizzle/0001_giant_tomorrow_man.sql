CREATE TABLE "clone_stats" (
	"day" date PRIMARY KEY NOT NULL,
	"count" integer NOT NULL,
	"uniques" integer NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
