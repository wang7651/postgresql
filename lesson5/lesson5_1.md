```SQL
SELECT SUM(新增確診數) AS 總確診數
FROM world
WHERE 日期 BETWEEN '2020-01-01' AND '2020-12-31';
```



**新增資料**

```
INSERT INTO student VALUES(1,'小白','歷史')
INSERT INTO student VALUES(2,'小黑','生物')
INSERT INTO student VALUES(3,'小綠',NULL)

INSERT INTO student(name,major) VALUES('小綠',NULL);
```

